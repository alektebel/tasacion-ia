"""Scraper de fotocasa.es (venta de vivienda). Uso de I+D; ver docs/obtencion-datos.md §7.

El listado incluye, por anuncio, coordenadas, dirección, CP, precio y características
(JSON en el <script id="__initial_props__">), así que no hace falta visitar las fichas.
Mismas reglas que pisos.com: robots.txt, 1 petición/s, parar ante 403/429.
"""

import json
import logging
import math
import re
from datetime import datetime, timezone

import psycopg

from tasacion.fuentes.pisoscom import Cliente
from tasacion.store import DATABASE_URL, save_bytes

log = logging.getLogger(__name__)

BASE = "https://www.fotocasa.es"
PORTAL = "fotocasa"
LISTADO = "/es/comprar/viviendas/espana/todas-las-zonas/l"
POR_PAGINA = 30
# El buscador deja de paginar (repite resultados) a partir de ~10.000.
MAX_RESULTADOS = 9900


def parse_listado(pagina: str) -> tuple[int | None, list[str], list[dict]]:
    """Devuelve (total, subzonas, anuncios). Las subzonas son las del primer nivel
    geográfico inferior con elementos (provincia -> comarca -> municipio -> distrito...)."""
    m = re.search(r'id="__initial_props__"[^>]*>(.*?)</script>', pagina, re.S)
    if not m:
        return None, [], []
    result = json.loads(m.group(1)).get("initialSearch", {}).get("result", {})
    subzonas = []
    for nivel in result.get("geographicSearch", []):
        if nivel.get("items"):
            subzonas = [i["url"] for i in nivel["items"] if i.get("url") and i.get("counter")]
            break
    return result.get("count"), subzonas, result.get("realEstates", [])


def _feature(anuncio: dict, key: str):
    for f in anuncio.get("features", []):
        if f["key"] == key:
            return f["value"]
    return None


def _guardar(conn: psycopg.Connection, anuncios: list[dict], raw_file_id: int) -> int:
    ahora = datetime.now(timezone.utc)
    nuevos = 0
    for a in anuncios:
        coords = a.get("coordinates") or {}
        addr = a.get("address") or {}
        lat, lon = coords.get("latitude"), coords.get("longitude")
        row = conn.execute(
            """
            INSERT INTO fuente.anuncio
                (portal, id_portal, url, operacion, tipologia, direccion, codigo_postal, geom,
                 geom_precision, planta, sup_construida, dormitorios, banos, ascensor,
                 anunciante_tipo, anunciante, primera_vez, ultima_vez)
            VALUES (%s, %s, %s, 'venta', %s, %s, %s,
                    CASE WHEN %s::float IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (portal, id_portal) DO UPDATE SET
                ultima_vez = EXCLUDED.ultima_vez, activo = true,
                geom = COALESCE(EXCLUDED.geom, fuente.anuncio.geom)
            RETURNING id, (xmax = 0)
            """,
            (
                PORTAL, str(a["id"]), BASE + (a.get("detail") or {}).get("es-ES", ""),
                a.get("buildingSubtype"), a.get("location"), addr.get("zipCode"),
                lat, lon, lat,
                "exacta" if coords.get("accuracy") == 1 else "aproximada",
                str(_feature(a, "floor")) if _feature(a, "floor") is not None else None,
                _feature(a, "surface"), _feature(a, "rooms"), _feature(a, "bathrooms"),
                _feature(a, "elevator") is not None or None,
                a.get("clientType"), a.get("clientAlias"), ahora, ahora,
            ),
        ).fetchone()
        nuevos += row[1]
        ultimo = conn.execute(
            "SELECT precio FROM fuente.anuncio_observacion WHERE anuncio_id = %s ORDER BY observado_en DESC LIMIT 1",
            (row[0],),
        ).fetchone()
        precio = a.get("rawPrice")
        if ultimo is None or (precio and float(ultimo[0] or 0) != precio):
            datos = {k: v for k, v in a.items() if k not in ("multimedia", "brandInfo", "phone")}
            conn.execute(
                "INSERT INTO fuente.anuncio_observacion (anuncio_id, observado_en, precio, datos, raw_file_id) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (row[0], ahora, precio, json.dumps(datos, ensure_ascii=False), raw_file_id),
            )
    return nuevos


def listados(pausa: float = 1.0, max_paginas: int | None = None) -> dict:
    """Recorre el listado bajando por zonas: el buscador sólo sirve ~10.000 resultados
    por consulta, así que las zonas más grandes se parten en sus subzonas."""
    cli = Cliente(pausa, base=BASE)
    stats = {"zonas": 0, "paginas": 0, "anuncios": 0, "nuevos": 0}
    visitadas: set[str] = set()
    pendientes = [LISTADO]
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        while pendientes:
            zona = pendientes.pop(0)
            if zona in visitadas:
                continue
            visitadas.add(zona)
            resp = cli.get(zona)
            total, subzonas, anuncios = parse_listado(resp.text)
            stats["zonas"] += 1
            subzonas = [z for z in subzonas if z not in visitadas]
            if total and total > MAX_RESULTADOS and subzonas:
                log.info("%s: %d resultados, bajo a %d subzonas", zona, total, len(subzonas))
                pendientes += subzonas
                continue
            n_paginas = math.ceil(min(total or 0, MAX_RESULTADOS) / POR_PAGINA) or 1
            if max_paginas:
                n_paginas = min(n_paginas, max_paginas)
            log.info("%s: %s resultados, %d páginas", zona, total, n_paginas)
            for n in range(1, n_paginas + 1):
                if n > 1:
                    resp = cli.get(f"{zona}/{n}")
                    _, _, anuncios = parse_listado(resp.text)
                if not anuncios:
                    break
                nombre = zona.removeprefix("/es/comprar/viviendas/").removesuffix("/l").replace("/", "_")
                f = save_bytes(
                    "fotocasa_listado", f"{nombre}_{n}.html", resp.content, str(resp.url), "text/html",
                    {"zona": zona, "pagina": n}, compress=True,
                )
                stats["nuevos"] += _guardar(conn, anuncios, f.raw_file_id)
                stats["paginas"] += 1
                stats["anuncios"] += len(anuncios)
            if stats["zonas"] % 50 == 0:
                log.info("fotocasa: %d zonas, %d páginas, %d nuevos", stats["zonas"], stats["paginas"], stats["nuevos"])
    return stats
