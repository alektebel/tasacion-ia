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


def parse_listado(pagina: str) -> tuple[int | None, list[dict]]:
    m = re.search(r'id="__initial_props__"[^>]*>(.*?)</script>', pagina, re.S)
    if not m:
        return None, []
    result = json.loads(m.group(1)).get("initialSearch", {}).get("result", {})
    return result.get("count"), result.get("realEstates", [])


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
    """Recorre el listado nacional. El orden no es estable entre páginas: cada ejecución
    recupera la mayoría de anuncios y las siguientes completan los huecos."""
    cli = Cliente(pausa, base=BASE)
    stats = {"paginas": 0, "anuncios": 0, "nuevos": 0}
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        total, _ = parse_listado(cli.get(LISTADO).text)
        n_paginas = math.ceil((total or 0) / POR_PAGINA)
        if max_paginas:
            n_paginas = min(n_paginas, max_paginas)
        log.info("fotocasa: %s anuncios, %d páginas", total, n_paginas)
        vacias = 0
        for n in range(1, n_paginas + 1):
            path = LISTADO if n == 1 else f"{LISTADO}/{n}"
            resp = cli.get(path)
            _, anuncios = parse_listado(resp.text)
            if not anuncios:
                vacias += 1
                if vacias >= 5:
                    log.warning("5 páginas vacías seguidas en %d; paro", n)
                    break
                continue
            vacias = 0
            f = save_bytes(
                "fotocasa_listado", f"espana_{n}.html", resp.content, str(resp.url), "text/html",
                {"pagina": n}, compress=True,
            )
            stats["nuevos"] += _guardar(conn, anuncios, f.raw_file_id)
            stats["paginas"] += 1
            stats["anuncios"] += len(anuncios)
            if n % 200 == 0:
                log.info("fotocasa: %d/%d páginas, %d nuevos", n, n_paginas, stats["nuevos"])
    return stats
