"""Sumarios diarios del BOE (API abierta): subastas administrativas en V-B y judiciales en IV.

El portal subastas.boe.es tiene robots.txt `Disallow: /`, así que se usa sólo la API abierta.
"""

import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import psycopg

from tasacion.store import DATABASE_URL, download, http_client, ya_descargado

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


ANUNCIO_URL = "https://www.boe.es/diario_boe/xml.php?id={id}"


def _items(nodo):
    if isinstance(nodo, dict):
        if "identificador" in nodo and "titulo" in nodo:
            yield nodo
        for v in nodo.values():
            yield from _items(v)
    elif isinstance(nodo, list):
        for v in nodo:
            yield from _items(v)


def _lista(x):
    return x if isinstance(x, list) else [x]


def anuncios_subasta() -> list[tuple[str, str]]:
    """(identificador, título) de los anuncios de la sección V-B que mencionan una subasta."""
    with psycopg.connect(DATABASE_URL) as conn:
        rutas = [r[0] for r in conn.execute("SELECT storage_uri FROM ingest.raw_file WHERE source = 'boe_sumario'")]
    encontrados = {}
    for ruta in rutas:
        try:
            sumario = json.loads(Path(ruta).read_text())["data"]["sumario"]
        except (OSError, ValueError, KeyError):
            continue
        for diario in _lista(sumario["diario"]):
            for seccion in _lista(diario["seccion"]):
                if seccion.get("codigo") != "5B":
                    continue
                for it in _items(seccion):
                    if "subasta" in it["titulo"].lower():
                        encontrados[it["identificador"]] = it["titulo"]
    return sorted(encontrados.items())


def descargar_anuncios(pausa: float = 0.5) -> dict:
    stats = {"descargados": 0, "omitidos": 0, "errores": 0}
    anuncios = anuncios_subasta()
    log.info("%d anuncios de subasta en los sumarios", len(anuncios))
    with http_client() as client:
        for i, (ident, titulo) in enumerate(anuncios, 1):
            url = ANUNCIO_URL.format(id=ident)
            if ya_descargado("boe_anuncio", url):
                stats["omitidos"] += 1
                continue
            try:
                download(client, "boe_anuncio", url, f"{ident}.xml", {"titulo": titulo})
                stats["descargados"] += 1
            except httpx.HTTPError as exc:
                stats["errores"] += 1
                log.warning("%s: %s", ident, exc)
            time.sleep(pausa)
            if i % 1000 == 0:
                log.info("anuncios: %d/%d", i, len(anuncios))
    return stats
