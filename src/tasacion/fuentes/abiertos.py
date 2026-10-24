"""Otras fuentes abiertas de contexto: renta, censo, alquiler, OSM, transporte, inspecciones
de edificios, certificados energéticos de más CCAA y open data municipal.

Todas son descargas directas sin identificación (verificadas el 2026-10-24, ver
docs/obtencion-datos.md). Las que cambian de nombre en cada edición se resuelven en tiempo
de ejecución.
"""

import csv
import io
import logging
import re

import httpx

from tasacion.store import download, http_client, ya_descargado

log = logging.getLogger(__name__)

EUSKADI = "https://opendata.euskadi.eus/contenidos/ds_registros"
BCN = "https://opendata-ajuntament.barcelona.cat/data/dataset"
REGISTRADORES = "https://opendata.registradores.org/data-integration"

# fuente -> [(url, nombre de fichero)]
DIRECTAS: dict[str, list[tuple[str, str]]] = {
    "ine_seccionado": [
        ("https://www.ine.es/prodyser/cartografia/seccionado_2026.zip", "seccionado_2026.zip"),
    ],
    "ine_censo2021": [
        ("https://www.ine.es/censos2021/C2021_Indicadores.csv", "C2021_Indicadores.csv"),
        ("https://www.ine.es/censos2021/indicadores_seccen_c2021.xlsx", "indicadores_seccen_c2021.xlsx"),
        ("https://www.ine.es/jaxi/files/tpx/es/csv_bdsc/59527.csv", "viviendas_anio_construccion_59527.csv"),
        ("https://www.ine.es/ftp/microdatos/censopv/cen21/CensoViviendas_2021.zip", "CensoViviendas_2021.zip"),
    ],
    "osm": [
        ("https://download.geofabrik.de/europe/spain-latest.osm.pbf", "spain-latest.osm.pbf"),
    ],
    "hacienda_irpf": [
        (
            "https://www.hacienda.gob.es/cdi/power%20bi/datos-visualizacionpowerbi-irpfmunicipios.xlsx",
            "irpf_municipios.xlsx",
        ),
    ],
    "registradores": [
        (
            f"{REGISTRADORES}/compraventas-comercial-trimestres-provincias-es/RP_ComprvCom_2007-2t2026.csv",
            "RP_ComprvCom_2007-2t2026.csv",
        ),
    ],
    "ite_euskadi": [
        (f"{EUSKADI}/inspeccion_tecnica_edificios/opendata/edificios-{t}.json", f"edificios-{t}.json")
        for t in ("bizkaia", "gipuzkoa", "araba")
    ],
    "iee_valencia": [
        (
            "https://terramapas.icv.gva.es/0801_GESIEE?request=GetFeature&service=WFS&version=2.0.0"
            f"&typename=GESIEE.{capa}&outputformat=csv",
            f"gesiee_{capa.lower()}.csv",
        )
        for capa in ("Informes", "Parcelas")
    ],
    "cee_euskadi": [
        (f"{EUSKADI}/certificados_eficie_energetica/opendata/certificados_{t}.csv", f"certificados_{t}.csv")
        for t in ("gipuzkoa", "bizkaia_bilbao", "araba")
    ],
    "cee_castilla_leon": [
        (
            "https://datosabiertos.jcyl.es/web/jcyl/risp/es/energia/certificados-eficiencia/1285094021912.csv",
            "cee_castilla_leon.csv",
        ),
    ],
    "madrid_opendata": [
        (
            "https://datos.madrid.es/dataset/300087-0-indicadores-distritos/resource/"
            "300087-0-indicadores-distritos-csv/download/acumulado.csv",
            "indicadores_distritos_barrios.csv",
        ),
        (
            "https://datos.madrid.es/dataset/300378-0-edificios-ruina/resource/"
            "300378-9-edificios-ruina/download/edificiosruinalegalfisica2026.xlsx",
            "edificios_ruina_2026.xlsx",
        ),
    ],
    "barcelona_opendata": [
        (
            f"{BCN}/e1c910f2-7f2c-447b-81b7-649b6bd08f39/resource/20b62da9-99f5-4010-b9cf-46b36cff8ea6"
            "/download/2026_loc_hab_valors.csv",
            "2026_loc_hab_valors.csv",
        ),
        (
            f"{BCN}/6e4e0b32-3347-442b-94d6-3d734b928815/resource/0d292f7d-0ad6-431d-8a54-6e9ad9d47ac3"
            "/download/2026_notaris_compravendes_trans_tip_us.csv",
            "2026_notaris_compravendes_trans_tip_us.csv",
        ),
    ],
    "gtfs": [
        ("https://servicios.emtmadrid.es:8443/gtfs/transitemt.zip", "emt_madrid.zip"),
        ("https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip", "renfe_cercanias.zip"),
        (
            "https://crtm.maps.arcgis.com/sharing/rest/content/items/885399f83408473c8d815e40c5e702b7/data",
            "crtm_interurbanos.zip",
        ),
        (
            "https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data",
            "crtm_metro.zip",
        ),
        (
            "https://crtm.maps.arcgis.com/sharing/rest/content/items/aaed26cc0ff64b0c947ac0bc3e033196/data",
            "crtm_metro_ligero.zip",
        ),
    ],
}

INE_TABLAS_ADRH = "https://servicios.ine.es/wstempus/js/ES/TABLAS_OPERACION/ADRH"
INE_CSV = "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/{id}.csv"
SERPAVI_PAGINA = "https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi"
MOBILITY_DB = "https://files.mobilitydatabase.org/feeds_v2.csv"


def _adrh(client: httpx.Client) -> list[tuple[str, str]]:
    """Tablas de renta media y mediana por sección censal (una por provincia + nacional)."""
    tablas = client.get(INE_TABLAS_ADRH).json()
    return [
        (INE_CSV.format(id=t["Id"]), f"adrh_{t['Id']}.csv")
        for t in tablas
        if "renta media y mediana" in t["Nombre"].lower()
    ]


def _serpavi(client: httpx.Client) -> list[tuple[str, str]]:
    html = client.get(SERPAVI_PAGINA).text
    urls = sorted(set(re.findall(r"https?://[^\"']+serpavi[^\"']+\.xlsx", html)))
    return [(u, "serpavi.xlsx") for u in urls[-1:]]


def _gtfs_mobility_db(client: httpx.Client) -> list[tuple[str, str]]:
    """Feeds GTFS españoles activos, desde el espejo de Mobility Database (sin API key)."""
    filas = csv.DictReader(io.StringIO(client.get(MOBILITY_DB).text))
    return [
        (f["urls.latest"], f"{f['id']}.zip")
        for f in filas
        if f["location.country_code"] == "ES" and f["data_type"] == "gtfs"
        and f["status"] == "active" and f["urls.latest"]
    ]


RESUELTAS = {"ine_adrh": _adrh, "serpavi": _serpavi, "gtfs": _gtfs_mobility_db}


def descargar(fuentes: list[str] | None = None) -> dict:
    stats = {}
    with http_client() as client:
        plan = {k: list(v) for k, v in DIRECTAS.items()}
        for fuente, resolver in RESUELTAS.items():
            if fuentes and fuente not in fuentes:
                continue
            try:
                plan.setdefault(fuente, []).extend(resolver(client))
            except Exception as exc:
                log.warning("%s: no se pudo resolver: %s", fuente, exc)
                stats[fuente] = f"error: {exc}"
        for fuente, ficheros in plan.items():
            if fuentes and fuente not in fuentes:
                continue
            ok = err = 0
            for url, nombre in ficheros:
                if ya_descargado(fuente, url):
                    ok += 1
                    continue
                try:
                    download(client, fuente, url, nombre)
                    ok += 1
                except Exception as exc:
                    err += 1
                    log.warning("%s %s: %s", fuente, nombre, exc)
            stats[fuente] = {"ok": ok, "errores": err}
            log.info("%s: %d ok, %d errores", fuente, ok, err)
    return stats
