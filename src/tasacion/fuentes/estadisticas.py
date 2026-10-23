"""Estadísticas de precio: MIVAU (XLS), INE (JSON) y Registradores open data (CSV)."""

import logging
import re
from datetime import date

from tasacion.store import download, http_client

log = logging.getLogger(__name__)

MIVAU_URL = "https://apps.fomento.gob.es/BoletinOnline2/sedal/{cod}.XLS"
MIVAU_SERIES = {
    "35101000": "valor tasado vivienda libre, provincias",
    "35103500": "valor tasado vivienda libre, municipios > 25.000 hab",
    "35103000": "número de tasaciones",
    "34010210": "transacciones de vivienda por municipio",
    "34010220": "transacciones de vivienda por municipio (desglose)",
    "34020150": "valor medio de transacciones, provincias",
}

INE_URL = "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{tabla}"
INE_TABLAS = {
    "80270": "IPV base 2025 por CCAA",
    "25171": "IPV base 2015 (serie histórica, termina 4T 2025)",
}

REGISTRADORES_FICHA = (
    "https://opendata.registradores.org/dataset/dataset/"
    "compraventas-de-inmuebles-uso-residencial-por-provincia"
)
# Último nombre conocido; el fichero se renombra cada trimestre.
REGISTRADORES_CSV = (
    "https://opendata.registradores.org/data-integration/"
    "compraventas-residencial-trimestres-provincias-es/RP_ComprvResid_2007-2t2026.csv"
)


def descargar() -> dict:
    hoy = date.today().isoformat()
    stats = {}
    with http_client() as client:
        for cod, desc in MIVAU_SERIES.items():
            f = download(client, "mivau", MIVAU_URL.format(cod=cod), f"{cod}.XLS", {"serie": desc})
            stats[f"mivau_{cod}"] = f.path.stat().st_size
        for tabla, desc in INE_TABLAS.items():
            f = download(
                client, "ine", INE_URL.format(tabla=tabla), f"ine_{tabla}_{hoy}.json", {"tabla": desc}
            )
            stats[f"ine_{tabla}"] = f.path.stat().st_size

        csv_url = REGISTRADORES_CSV
        try:
            html = client.get(REGISTRADORES_FICHA, timeout=30).text
            encontrados = sorted(set(re.findall(r"https?://[^\"'\s]+RP_ComprvResid[^\"'\s]+\.csv", html)))
            if encontrados:
                csv_url = encontrados[-1]
        except Exception as exc:
            log.warning("no se pudo leer la ficha de Registradores, uso la URL conocida: %s", exc)
        f = download(client, "registradores", csv_url, csv_url.rsplit("/", 1)[1])
        stats["registradores"] = f.path.stat().st_size
    return stats
