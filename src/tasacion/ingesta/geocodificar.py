"""Geolocalización de los testigos de una tasación.

Los informes escriben las direcciones de cualquier manera («SAN PABLO (DE), Nº 55», «Calle,
Dulce Chacón, Nº 23, Planta 18», «CARRE ALGEZAR,10-MONCADA/VALENCIA»), así que primero un
modelo ligero las normaliza a tipo de vía, nombre, número y CP. Después, en cascada:

1. Referencia catastral del testigo -> centroide de la parcela (fuente.catastro_parcela).
2. Callejero del Catastro cargado en local (fuente.catastro_direccion): CP + nombre de vía por
   trigramas + número. Da también la parcela, útil para cruzar el testigo con Catastro.
3. CartoCiudad, filtrando por CP.

Sin número de portal se toma el centro de la vía (precisión «calle»). Lo que no se encuentra se
queda sin punto: mejor nada que un punto inventado en el centro del CP.
"""

import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher

import psycopg
from psycopg.rows import dict_row

from tasacion import llm
from tasacion.fuentes import cartociudad
from tasacion.store import DATABASE_URL

log = logging.getLogger(__name__)

SIMILITUD_MIN = 0.5

SISTEMA = """\
Normalizas direcciones postales españolas copiadas de informes de tasación para buscarlas en el \
callejero del Catastro. Devuelve un objeto JSON con las claves tipo_via, nombre_via, numero, \
codigo_postal y municipio (null si no consta).

- tipo_via: abreviatura del Catastro: CL calle (también carrer, carre, rúa, kalea), AV avenida, \
PZ plaza, PS paseo, CR carretera, CM camino, TR travesía, RD ronda, GL glorieta, UR urbanización, \
PJ pasaje, CJ callejón, BO barrio, PG polígono. null si la dirección no lo dice.
- nombre_via: en mayúsculas y sin tildes, sin el tipo de vía, sin partículas iniciales entre \
paréntesis («SAN PABLO (DE)» -> «SAN PABLO») y sin aclaraciones entre paréntesis \
(«RAMON PAYA (METGE I MUSIC)» -> «RAMON PAYA»). No traduzcas ni corrijas el nombre.
- numero: sólo el número de portal («Nº 23» -> «23»); null si no hay. Ignora planta y puerta.
- codigo_postal y municipio: los de la dirección; si no constan, los del contexto."""


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def _numero(texto) -> str | None:
    m = re.search(r"0*(\d+)", str(texto or ""))
    return m.group(1) if m else None


def normalizar(direccion: str, codigo_postal: str | None, municipio: str | None) -> dict:
    contexto = f"CP {codigo_postal or '?'}, municipio {municipio or '?'}"
    d = llm.json_chat(SISTEMA, f"Dirección: {direccion}\nContexto: {contexto}")
    d = {k: d.get(k) for k in ("tipo_via", "nombre_via", "numero", "codigo_postal", "municipio")}
    d["nombre_via"] = _plano(d["nombre_via"]) if d["nombre_via"] else None
    d["numero"] = _numero(d["numero"])
    d["codigo_postal"] = d["codigo_postal"] or codigo_postal
    return d


def _por_catastro(conn: psycopg.Connection, d: dict) -> dict | None:
    if not (d["codigo_postal"] and d["nombre_via"]):
        return None
    via = conn.execute(
        """
        SELECT tipo_via, nombre_via, similarity(nombre_via, %(nombre)s) AS sim, count(*) AS n
        FROM fuente.catastro_direccion
        WHERE codigo_postal = %(cp)s AND similarity(nombre_via, %(nombre)s) >= %(min)s
        GROUP BY 1, 2
        ORDER BY sim DESC, (tipo_via = %(tipo)s) DESC, n DESC LIMIT 1
        """,
        {"cp": d["codigo_postal"], "nombre": d["nombre_via"], "tipo": d["tipo_via"], "min": SIMILITUD_MIN},
    ).fetchone()
    if not via:
        return None
    filtro = {"cp": d["codigo_postal"], "tipo": via["tipo_via"], "nombre": via["nombre_via"]}
    if d["numero"]:
        portal = conn.execute(
            """
            SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon, ref_catastral_14 AS rc14
            FROM fuente.catastro_direccion
            WHERE codigo_postal = %(cp)s AND tipo_via = %(tipo)s AND nombre_via = %(nombre)s
              AND ltrim(numero, '0') = %(num)s
            LIMIT 1
            """, filtro | {"num": d["numero"]},
        ).fetchone()
        if portal:
            return portal | {"fuente": "catastro_direccion", "precision": "portal",
                             "via": f"{via['tipo_via']} {via['nombre_via']}"}
    centro = conn.execute(
        """
        SELECT ST_Y(c) AS lat, ST_X(c) AS lon FROM (
            SELECT ST_Centroid(ST_Collect(geom)) AS c FROM fuente.catastro_direccion
            WHERE codigo_postal = %(cp)s AND tipo_via = %(tipo)s AND nombre_via = %(nombre)s) s
        """, filtro,
    ).fetchone()
    return centro | {"rc14": None, "fuente": "catastro_direccion", "precision": "calle",
                     "via": f"{via['tipo_via']} {via['nombre_via']}"}


def _por_cartociudad(d: dict) -> dict | None:
    if not d["nombre_via"]:
        return None
    texto = " ".join(x for x in (d["nombre_via"], d["numero"]) if x)
    for c in cartociudad.candidatos(texto, d["codigo_postal"]):
        if c.get("type") not in ("portal", "callejero") or c.get("lat") is None:
            continue
        nombre = _plano(re.sub(r"\s+\d+.*$", "", c.get("address") or "").removeprefix(c.get("tip_via") or "").strip())
        if SequenceMatcher(None, nombre, d["nombre_via"]).ratio() < 0.6:
            continue
        exacto = d["numero"] and str(c.get("portalNumber")) == d["numero"] and not c.get("noNumber")
        rc = c.get("refCatastral")
        return {"lat": c["lat"], "lon": c["lng"], "rc14": rc[:14] if exacto and rc else None,
                "fuente": "cartociudad", "precision": "portal" if exacto else "calle",
                "via": f"{c.get('tip_via')} {nombre}"}
    return None


def _por_rc(conn: psycopg.Connection, rc: str | None) -> dict | None:
    if not rc or len(rc) < 14:
        return None
    fila = conn.execute(
        "SELECT ST_Y(ST_PointOnSurface(geom)) AS lat, ST_X(ST_PointOnSurface(geom)) AS lon "
        "FROM fuente.catastro_parcela WHERE ref_catastral_14 = %s", (rc[:14].upper(),),
    ).fetchone()
    return fila and fila | {"rc14": rc[:14].upper(), "fuente": "catastro_rc", "precision": "parcela"}


def testigos(tasacion_ids: list[int] | None = None, rehacer: bool = False) -> dict:
    """Geolocaliza los testigos sin punto (o todos, con `rehacer`) de las tasaciones indicadas."""
    stats = {"testigos": 0, "catastro_rc": 0, "catastro_direccion": 0, "cartociudad": 0, "sin_punto": 0}
    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        filas = conn.execute(
            """
            SELECT t.id, t.direccion, t.codigo_postal, t.ref_catastral, f.municipio, f.codigo_postal AS cp_finca
            FROM tasacion.testigo t JOIN tasacion.finca f ON f.id = t.finca_id
            WHERE (%(ids)s::bigint[] IS NULL OR f.tasacion_id = ANY(%(ids)s))
              AND (%(rehacer)s OR t.geom IS NULL)
            ORDER BY t.id
            """, {"ids": tasacion_ids, "rehacer": rehacer},
        ).fetchall()
        for t in filas:
            stats["testigos"] += 1
            d = None
            punto = _por_rc(conn, t["ref_catastral"])
            if not punto and t["direccion"]:
                d = normalizar(t["direccion"], t["codigo_postal"] or t["cp_finca"], t["municipio"])
                punto = _por_catastro(conn, d)
                # El callejero local no tiene el portal (o ni la vía): CartoCiudad puede afinar.
                if not punto or (punto["precision"] == "calle" and d["numero"]):
                    externo = _por_cartociudad(d)
                    if externo and (not punto or externo["precision"] == "portal"):
                        punto = externo
            if not punto:
                stats["sin_punto"] += 1
                log.info("testigo %d sin punto: %r -> %s", t["id"], t["direccion"], d)
                conn.execute("UPDATE tasacion.testigo SET direccion_normalizada = %s WHERE id = %s",
                             (json.dumps(d, ensure_ascii=False) if d else None, t["id"]))
                continue
            stats[punto["fuente"]] += 1
            log.info("testigo %d: %r -> %s (%s, %s)", t["id"], t["direccion"], punto.get("via", punto["rc14"]),
                     punto["fuente"], punto["precision"])
            conn.execute(
                """
                UPDATE tasacion.testigo SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    geocodificacion_fuente = %s, geocodificacion_precision = %s,
                    direccion_normalizada = %s, ref_catastral_14_geo = %s
                WHERE id = %s
                """,
                (punto["lon"], punto["lat"], punto["fuente"], punto["precision"],
                 json.dumps(d, ensure_ascii=False) if d else None, punto["rc14"], t["id"]),
            )
    return stats
