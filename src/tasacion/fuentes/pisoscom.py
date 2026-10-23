"""Scraper de pisos.com (venta de vivienda). Uso de I+D; ver docs/obtencion-datos.md §7.

- Respeta robots.txt (las rutas /venta/<zona>/<n>/ y /comprar/<ficha>/ están permitidas).
- Una petición por segundo, sin paralelismo ni evasión de bloqueos: si el portal responde
  403/429 se para.
- La paginación está limitada a 100 páginas (3.000 anuncios) por zona; las zonas más
  grandes se recorren bajando por sus subzonas (`descending-geo__result`).

Fase 1 (`listados`): precio, superficie, habitaciones y URL de cada anuncio.
Fase 2 (`fichas`): coordenadas y características completas, sólo de anuncios sin geometría.
"""

import html
import json
import logging
import math
import re
import time
from datetime import datetime, timezone

import httpx
import psycopg

from tasacion.store import DATABASE_URL, http_client, save_bytes

log = logging.getLogger(__name__)

BASE = "https://www.pisos.com"
PORTAL = "pisos.com"
POR_PAGINA = 30
MAX_PAGINAS = 100
PROVINCIAS = [
    "a_coruna", "alava_araba", "albacete", "alicante", "almeria", "asturias", "avila",
    "badajoz", "barcelona", "burgos", "caceres", "cadiz", "cantabria", "castellon_castello",
    "ceuta", "ciudad_real", "cordoba", "cuenca", "girona", "granada", "guadalajara",
    "guipuzcoa_gipuzkoa", "huelva", "huesca", "islas_baleares_illes_balears", "jaen",
    "la_rioja", "las_palmas", "leon", "lleida", "lugo", "madrid", "malaga", "melilla",
    "murcia", "navarra_nafarroa", "ourense", "palencia", "pontevedra", "salamanca",
    "santa_cruz_de_tenerife", "segovia", "sevilla", "soria", "tarragona", "teruel", "toledo",
    "valencia", "valladolid", "vizcaya_bizkaia", "zamora", "zaragoza",
]


class Bloqueado(Exception):
    pass


class Cliente:
    """Cliente HTTP con pausa mínima entre peticiones."""

    def __init__(self, pausa: float = 1.0, base: str = BASE):
        self.http = http_client(headers={"Accept-Language": "es-ES,es;q=0.9"})
        self.pausa = pausa
        self.base = base
        self._ultima = 0.0

    def get(self, path: str) -> httpx.Response:
        espera = self.pausa - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        for intento in range(3):
            try:
                resp = self.http.get(self.base + path)
                break
            except httpx.TransportError:
                if intento == 2:
                    raise
                time.sleep(10 * (intento + 1))
        self._ultima = time.monotonic()
        if resp.status_code in (403, 429):
            raise Bloqueado(f"{resp.status_code} en {path}")
        return resp


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def _num(texto: str | None) -> float | None:
    if not texto:
        return None
    m = re.search(r"\d[\d.]*(?:,\d+)?", texto)
    return float(m.group(0).replace(".", "").replace(",", ".")) if m else None


def _texto(bloque: str, clase: str) -> str | None:
    m = re.search(rf'class="{clase}[^"]*"[^>]*>\s*([^<]+)', bloque)
    return html.unescape(m.group(1)).strip() if m else None


def parse_listado(pagina: str) -> tuple[int | None, list[str], list[dict]]:
    """Devuelve (total de resultados, subzonas, anuncios)."""
    m = re.search(r"([\d.]+) resultados", pagina)
    total = int(m.group(1).replace(".", "")) if m else None
    subzonas = sorted(set(re.findall(r'href="(/venta/[a-z0-9_-]+/)" class="descending-geo__result"', pagina)))
    anuncios = []
    for bloque in pagina.split('class="ad-preview ')[1:]:
        id_m = re.search(r'data-id="([\d.]+)"', bloque)
        href_m = re.search(r'data-lnk-href="([^"]+)"', bloque)
        if not id_m or not href_m:
            continue
        chars = [html.unescape(c).strip() for c in re.findall(r'class="ad-preview__char[^"]*"[^>]*>\s*([^<]+)', bloque)]
        precio_m = re.search(r'data-ad-price="(\d+)"', bloque)
        anuncio = {
            "id_portal": id_m.group(1),
            "url": BASE + href_m.group(1),
            "precio": float(precio_m.group(1)) if precio_m else _num(_texto(bloque, "ad-preview__price")),
            "titulo": _texto(bloque, "ad-preview__title"),
            "subtitulo": _texto(bloque, "ad-preview__subtitle"),
            "chars": chars,
        }
        for c in chars:
            if "hab" in c:
                anuncio["dormitorios"] = int(_num(c))
            elif "baño" in c:
                anuncio["banos"] = int(_num(c))
            elif "m²" in c:
                anuncio["sup_construida"] = _num(c)
        anuncios.append(anuncio)
    return total, subzonas, anuncios


def parse_ficha(pagina: str) -> dict:
    datos: dict = {}
    m = re.search(r"latitude=(-?[\d.]+)&amp;longitude=(-?[\d.]+)", pagina)
    if m:
        datos["lat"], datos["lon"] = float(m.group(1)), float(m.group(2))
    caracteristicas = {
        html.unescape(k).strip().rstrip(":"): html.unescape(v).strip()
        for k, v in re.findall(
            r'class="features__label">([^<]*)</span>\s*<span class="features__value">([^<]*)', pagina
        )
    }
    datos["caracteristicas"] = caracteristicas
    h1 = re.search(r"<h1[^>]*>([^<]+)", pagina)
    datos["titulo"] = html.unescape(h1.group(1)).strip() if h1 else None
    loc = re.search(r'class="details__block[^"]*"[^>]*>\s*<p[^>]*>([^<]+)', pagina)
    datos["localizacion"] = html.unescape(loc.group(1)).strip() if loc else None
    desc = re.search(r'class="description__content"[^>]*>(.*?)</div>', pagina, re.S)
    if desc:
        datos["descripcion"] = html.unescape(re.sub(r"<[^>]+>", " ", desc.group(1))).strip()
    return datos


def _planta(texto: str | None) -> str | None:
    return texto.replace("ª", "").strip() if texto else None


# ---------------------------------------------------------------------------
# persistencia
# ---------------------------------------------------------------------------

def _guardar_listado(conn: psycopg.Connection, anuncios: list[dict], zona: str, raw_file_id: int):
    ahora = datetime.now(timezone.utc)
    for a in anuncios:
        row = conn.execute(
            """
            INSERT INTO fuente.anuncio
                (portal, id_portal, url, operacion, direccion, sup_construida, dormitorios, banos,
                 primera_vez, ultima_vez)
            VALUES (%s, %s, %s, 'venta', %s, %s, %s, %s, %s, %s)
            ON CONFLICT (portal, id_portal) DO UPDATE SET
                ultima_vez = EXCLUDED.ultima_vez, activo = true,
                sup_construida = COALESCE(EXCLUDED.sup_construida, fuente.anuncio.sup_construida)
            RETURNING id
            """,
            (PORTAL, a["id_portal"], a["url"], a.get("titulo"), a.get("sup_construida"),
             a.get("dormitorios"), a.get("banos"), ahora, ahora),
        ).fetchone()
        ultimo = conn.execute(
            "SELECT precio FROM fuente.anuncio_observacion WHERE anuncio_id = %s ORDER BY observado_en DESC LIMIT 1",
            (row[0],),
        ).fetchone()
        if ultimo is None or (a["precio"] is not None and float(ultimo[0] or 0) != a["precio"]):
            conn.execute(
                "INSERT INTO fuente.anuncio_observacion (anuncio_id, observado_en, precio, datos, raw_file_id) VALUES (%s, %s, %s, %s, %s)",
                (row[0], ahora, a["precio"], json.dumps(a | {"zona": zona}, ensure_ascii=False), raw_file_id),
            )


def _guardar_ficha(conn: psycopg.Connection, anuncio_id: int, f: dict, raw_file_id: int):
    c = f["caracteristicas"]
    conn.execute(
        """
        UPDATE fuente.anuncio SET
            geom = CASE WHEN %(lat)s::float IS NULL THEN geom
                        ELSE ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) END,
            geom_precision = CASE WHEN %(lat)s::float IS NULL THEN geom_precision ELSE 'portal' END,
            direccion = COALESCE(%(dir)s, direccion),
            sup_construida = COALESCE(%(sc)s, sup_construida),
            sup_util = COALESCE(%(su)s, sup_util),
            dormitorios = COALESCE(%(dor)s, dormitorios),
            banos = COALESCE(%(ban)s, banos),
            planta = COALESCE(%(pl)s, planta),
            estado = COALESCE(%(est)s, estado),
            tipologia = COALESCE(%(tip)s, tipologia)
        WHERE id = %(id)s
        """,
        {
            "id": anuncio_id, "lat": f.get("lat"), "lon": f.get("lon"),
            "dir": f.get("localizacion"),
            "sc": _num(c.get("Superficie construida")), "su": _num(c.get("Superficie útil")),
            "dor": _num(c.get("Habitaciones")), "ban": _num(c.get("Baños")),
            "pl": _planta(c.get("Planta")), "est": c.get("Conservación"),
            "tip": (f.get("titulo") or "").split(" en ")[0] or None,
        },
    )
    conn.execute(
        """
        UPDATE fuente.anuncio_observacion SET datos = datos || %s::jsonb
        WHERE anuncio_id = %s AND observado_en = (
            SELECT max(observado_en) FROM fuente.anuncio_observacion WHERE anuncio_id = %s)
        """,
        (json.dumps({"ficha": f, "ficha_raw_file_id": raw_file_id}, ensure_ascii=False), anuncio_id, anuncio_id),
    )


# ---------------------------------------------------------------------------
# fases
# ---------------------------------------------------------------------------

def listados(provincias: list[str] | None = None, pausa: float = 1.0) -> dict:
    cli = Cliente(pausa)
    stats = {"paginas": 0, "anuncios": 0, "zonas": 0}
    visitadas: set[str] = set()
    pendientes = [f"/venta/pisos-{p}/" for p in (provincias or PROVINCIAS)]
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        while pendientes:
            zona = pendientes.pop(0)
            if zona in visitadas:
                continue
            visitadas.add(zona)
            resp = cli.get(zona)
            if resp.status_code != 200 or str(resp.url).rstrip("/") != (BASE + zona).rstrip("/"):
                log.warning("zona %s: %s -> %s", zona, resp.status_code, resp.url)
                continue
            total, subzonas, anuncios = parse_listado(resp.text)
            stats["zonas"] += 1
            if total and total > POR_PAGINA * MAX_PAGINAS and subzonas:
                log.info("%s: %d resultados, bajo a %d subzonas", zona, total, len(subzonas))
                pendientes += [s for s in subzonas if s not in visitadas]
                continue
            n_paginas = min(MAX_PAGINAS, math.ceil((total or 0) / POR_PAGINA)) or 1
            log.info("%s: %s resultados, %d páginas", zona, total, n_paginas)
            for n in range(1, n_paginas + 1):
                if n > 1:
                    path = f"{zona}{n}/"
                    resp = cli.get(path)
                    if str(resp.url).rstrip("/") != (BASE + path).rstrip("/"):
                        break  # redirige a la página 1: fin de la paginación
                    _, _, anuncios = parse_listado(resp.text)
                f = save_bytes(
                    "pisoscom_listado", f"{zona.strip('/').replace('/', '_')}_{n}.html",
                    resp.content, str(resp.url), "text/html", {"zona": zona, "pagina": n}, compress=True,
                )
                _guardar_listado(conn, anuncios, zona, f.raw_file_id)
                stats["paginas"] += 1
                stats["anuncios"] += len(anuncios)
                if not anuncios:
                    break
    return stats


def fichas(limite: int | None = None, pausa: float = 1.0) -> dict:
    cli = Cliente(pausa)
    stats = {"fichas": 0, "con_coordenadas": 0, "errores": 0}
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        pendientes = conn.execute(
            "SELECT id, url FROM fuente.anuncio WHERE portal = %s AND geom IS NULL AND activo "
            "ORDER BY primera_vez DESC LIMIT %s",
            (PORTAL, limite),
        ).fetchall()
        log.info("%d fichas pendientes", len(pendientes))
        for i, (anuncio_id, url) in enumerate(pendientes, 1):
            path = url.removeprefix(BASE)
            resp = cli.get(path)
            if resp.status_code == 404 or str(resp.url).rstrip("/") != url.rstrip("/"):
                conn.execute("UPDATE fuente.anuncio SET activo = false WHERE id = %s", (anuncio_id,))
                continue
            if resp.status_code != 200:
                stats["errores"] += 1
                continue
            f = parse_ficha(resp.text)
            raw = save_bytes(
                "pisoscom_ficha", f"{anuncio_id}.html", resp.content, url, "text/html", compress=True
            )
            _guardar_ficha(conn, anuncio_id, f, raw.raw_file_id)
            stats["fichas"] += 1
            stats["con_coordenadas"] += "lat" in f
            if i % 500 == 0:
                log.info("fichas: %d/%d", i, len(pendientes))
    return stats
