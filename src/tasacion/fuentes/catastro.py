"""Catastro INSPIRE: ZIPs con GML por municipio (parcelas CP, edificios BU, direcciones AD).

Estructura: feed ATOM raíz -> un feed por gerencia/provincia -> un ZIP por municipio.
No incluye País Vasco ni Navarra (catastros forales).
"""

import logging
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, urlparse

import httpx

from tasacion.store import download, http_client, ya_descargado

log = logging.getLogger(__name__)

BASE = "https://www.catastro.hacienda.gob.es/INSPIRE/"
FEEDS = {
    "CP": BASE + "CadastralParcels/ES.SDGC.CP.atom.xml",
    "BU": BASE + "buildings/ES.SDGC.BU.atom.xml",
    "AD": BASE + "Addresses/ES.SDGC.AD.atom.xml",
}
ATOM = "{http://www.w3.org/2005/Atom}"


def _https(url: str) -> str:
    return "https://" + url.removeprefix("http://") if url.startswith("http://") else url


def _enlaces(client: httpx.Client, url: str, sufijo: str) -> list[str]:
    resp = client.get(url)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)  # respeta el encoding declarado (ISO-8859-1 en provincias)
    hrefs = []
    for entry in root.iter(ATOM + "entry"):
        for link in entry.iter(ATOM + "link"):
            href = link.get("href", "")
            if href.lower().endswith(sufijo) and href not in hrefs:
                hrefs.append(_https(href))
    return hrefs


def _provincia(url: str) -> str:
    # .../INSPIRE/<capa>/<PP>/...
    return urlparse(url).path.split("/")[3]


def listar_zips(client: httpx.Client, capa: str, provincias: list[str] | None) -> list[str]:
    feeds = _enlaces(client, FEEDS[capa], ".xml")
    if provincias:
        feeds = [f for f in feeds if _provincia(f) in provincias]
    zips = []
    for feed in feeds:
        zips += _enlaces(client, feed, ".zip")
        time.sleep(0.2)
    return zips


def descargar(capas: list[str], provincias: list[str] | None = None, workers: int = 4) -> dict:
    stats = {"descargados": 0, "omitidos": 0, "errores": 0, "bytes": 0}
    with http_client() as client:
        for capa in capas:
            source = f"catastro_inspire_{capa.lower()}"
            zips = listar_zips(client, capa, provincias)
            pendientes = [z for z in zips if not ya_descargado(source, z)]
            stats["omitidos"] += len(zips) - len(pendientes)
            log.info("%s: %d municipios, %d pendientes", capa, len(zips), len(pendientes))

            def bajar(url: str):
                nombre = unquote(url.rsplit("/", 1)[1])
                meta = {"capa": capa, "provincia": _provincia(url)}
                for intento in range(3):
                    try:
                        return download(client, source, url, nombre, meta)
                    except httpx.HTTPError:
                        if intento == 2:
                            raise
                        time.sleep(5 * (intento + 1))

            with ThreadPoolExecutor(workers) as pool:
                futuros = {pool.submit(bajar, z): z for z in pendientes}
                for i, fut in enumerate(as_completed(futuros), 1):
                    try:
                        f = fut.result()
                        stats["descargados"] += 1
                        stats["bytes"] += f.path.stat().st_size
                    except Exception as exc:  # seguimos con el resto; se reintenta en la próxima ejecución
                        stats["errores"] += 1
                        log.warning("error %s: %s", futuros[fut], exc)
                    if i % 200 == 0:
                        log.info("%s: %d/%d", capa, i, len(pendientes))
    return stats
