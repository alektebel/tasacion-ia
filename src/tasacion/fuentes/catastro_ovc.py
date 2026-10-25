"""Servicios web del Catastro (OVC) por referencia catastral, con caché en fuente.catastro_inmueble.

Gratuitos pero vigilados: con abuso el Catastro bloquea la IP ~10 días. Por eso cada RC se
consulta una sola vez y se respeta una pausa mínima entre peticiones.
"""

import json
import logging
import time

import psycopg

from tasacion.store import DATABASE_URL, http_client

log = logging.getLogger(__name__)

BASE = "https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero"
DNPRC = BASE + "/COVCCallejero.svc/json/Consulta_DNPRC"
CPMRC = BASE + "/COVCCoordenadas.svc/json/Consulta_CPMRC"
PAUSA = 1.5
_ultima = 0.0


def _get(url: str, params: dict) -> dict:
    global _ultima
    espera = PAUSA - (time.monotonic() - _ultima)
    if espera > 0:
        time.sleep(espera)
    with http_client() as client:
        resp = client.get(url, params=params, timeout=30)
    _ultima = time.monotonic()
    resp.raise_for_status()
    return resp.json()


def _num(texto) -> float | None:
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def inmueble(rc20: str) -> dict | None:
    """Uso, superficie (con comunes), año, CP y unidades constructivas de un inmueble."""
    rc20 = rc20.replace(" ", "").upper()
    with psycopg.connect(DATABASE_URL) as conn:
        fila = conn.execute(
            "SELECT detalle FROM fuente.catastro_inmueble WHERE ref_catastral_20 = %s AND origen = 'ovc'", (rc20,)
        ).fetchone()
        if fila:
            return fila[0] or None
        datos = _get(DNPRC, {"RefCat": rc20}).get("consulta_dnprcResult", {})
        bi = (datos.get("bico") or {}).get("bi")
        if not bi:
            # RC inexistente: se cachea como vacío para no repetir la consulta.
            log.info("RC %s no encontrada en Catastro: %s", rc20, datos.get("lerr"))
            conn.execute(
                "INSERT INTO fuente.catastro_inmueble (ref_catastral_20, ref_catastral_14, origen, detalle) "
                "VALUES (%s, %s, 'ovc', '{}') ON CONFLICT DO NOTHING",
                (rc20[:20].ljust(20), rc20[:14]),
            )
            return None
        debi = bi.get("debi", {})
        lourb = bi.get("dt", {}).get("locs", {}).get("lous", {}).get("lourb", {})
        loint = lourb.get("loint", {})
        lcons = (datos.get("bico") or {}).get("lcons") or []
        detalle = {
            "uso": debi.get("luso"),
            "sup": _num(debi.get("sfc")),
            "anio": int(debi["ant"]) if str(debi.get("ant", "")).isdigit() else None,
            "coef_participacion": _num(debi.get("cpt")),
            "codigo_postal": lourb.get("dp"),
            "direccion": bi.get("ldt"),
            "municipio": bi.get("dt", {}).get("nm"),
            "provincia": bi.get("dt", {}).get("np"),
            "construcciones": [
                {"uso": c.get("lcd"), "sup": _num((c.get("dfcons") or {}).get("stl"))} for c in lcons
            ],
        }
        conn.execute(
            """
            INSERT INTO fuente.catastro_inmueble
                (ref_catastral_20, ref_catastral_14, uso, sup_construida, coef_participacion,
                 anio_construccion, escalera, planta, puerta, detalle, origen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ovc')
            ON CONFLICT (ref_catastral_20) DO UPDATE SET detalle = EXCLUDED.detalle, consultado_en = now()
            """,
            (rc20, rc20[:14], detalle["uso"], detalle["sup"], detalle["coef_participacion"], detalle["anio"],
             loint.get("es"), loint.get("pt"), loint.get("pu"), json.dumps(detalle, ensure_ascii=False)),
        )
        return detalle


def coordenadas(rc14: str) -> tuple[float, float] | None:
    """(lat, lon) del centroide de la parcela: primero la tabla cargada, si no el servicio OVC."""
    rc14 = rc14[:14].upper()
    with psycopg.connect(DATABASE_URL) as conn:
        fila = conn.execute(
            "SELECT ST_Y(ST_PointOnSurface(geom)), ST_X(ST_PointOnSurface(geom)) "
            "FROM fuente.catastro_parcela WHERE ref_catastral_14 = %s", (rc14,)
        ).fetchone()
    if fila:
        return fila[0], fila[1]
    res = _get(CPMRC, {"SRS": "EPSG:4326", "RefCat": rc14}).get("Consulta_CPMRCResult", {})
    coord = ((res.get("coordenadas") or {}).get("coord") or [None])[0]
    if not coord:
        return None
    geo = coord.get("geo", {})
    return float(geo["ycen"]), float(geo["xcen"])
