"""Geocodificador de CartoCiudad (IGN/CNIG): dirección -> portal o vía, con referencia catastral.

Gratuito y sin clave. El filtro por municipio de la API no funciona con nombres; se filtra por
código postal y se comprueba el resultado.
"""

import logging
import time

from tasacion.store import http_client

log = logging.getLogger(__name__)

CANDIDATOS = "https://www.cartociudad.es/geocoder/api/geocoder/candidates"
PAUSA = 0.5
_ultima = 0.0


def candidatos(texto: str, codigo_postal: str | None = None, limite: int = 5) -> list[dict]:
    global _ultima
    espera = PAUSA - (time.monotonic() - _ultima)
    if espera > 0:
        time.sleep(espera)
    params = {"q": texto, "limit": limite}
    if codigo_postal:
        params["cod_postal_filter"] = codigo_postal
    with http_client() as client:
        resp = client.get(CANDIDATOS, params=params, timeout=30)
    _ultima = time.monotonic()
    resp.raise_for_status()
    return resp.json() or []
