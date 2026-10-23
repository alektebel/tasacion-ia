"""Sumarios diarios del BOE (API de datos abiertos). Los anuncios de subastas van en la sección V-B.

El portal subastas.boe.es tiene robots.txt `Disallow: /`, así que se usa sólo la API abierta.
"""

import logging
import time
from datetime import date, timedelta

import httpx

from tasacion.store import download, http_client, ya_descargado

log = logging.getLogger(__name__)

SUMARIO_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"
# El portal de subastas electrónicas del BOE arranca en octubre de 2015.
DESDE = date(2015, 10, 15)


def descargar(desde: date = DESDE, hasta: date | None = None, pausa: float = 0.5) -> dict:
    hasta = hasta or date.today()
    stats = {"descargados": 0, "omitidos": 0, "sin_boe": 0, "errores": 0}
    with http_client(headers={"Accept": "application/json"}) as client:
        dia = desde
        while dia <= hasta:
            url = SUMARIO_URL.format(fecha=dia.strftime("%Y%m%d"))
            if ya_descargado("boe_sumario", url):
                stats["omitidos"] += 1
            else:
                try:
                    download(client, "boe_sumario", url, f"{dia:%Y%m%d}.json", {"fecha": dia.isoformat()})
                    stats["descargados"] += 1
                except httpx.HTTPStatusError as exc:
                    # Domingos y festivos sin BOE devuelven 404.
                    key = "sin_boe" if exc.response.status_code == 404 else "errores"
                    stats[key] += 1
                except httpx.HTTPError as exc:
                    stats["errores"] += 1
                    log.warning("%s: %s", dia, exc)
                time.sleep(pausa)
            dia += timedelta(days=1)
    return stats
