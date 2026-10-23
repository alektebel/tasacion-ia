"""Registros abiertos de certificados de eficiencia energética (incluyen ref. catastral)."""

import logging

from tasacion.store import download, http_client

log = logging.getLogger(__name__)

# CCAA con portal CKAN: las URLs de recursos llevan UUID, se resuelven con package_show.
CKAN = {
    "madrid": (
        "https://datos.comunidad.madrid/api/3/action/package_show",
        "registro_certificados_eficiencia_energetica",
    ),
    "valencia": (
        "https://dadesobertes.gva.es/api/3/action/package_show",
        "med-eficiencia-energetica-edificis-ivace",
    ),
    "aragon": (
        "https://opendata.aragon.es/ckan/api/3/action/package_show",
        "registro-de-certificacion-de-eficiencia-energetica-de-edificios-de-aragon",
    ),
}
DIRECTAS = {
    "canarias": "https://datos.canarias.es/catalogos/general/dataset/ca2b3a6c-241b-4fe1-ba6b-f35257ce9604/resource/7094974b-2642-45bf-a5c7-636692d2b3ec/download/rcee.csv",
    # Export completo de Socrata (1,3 M filas).
    "cataluna": "https://analisi.transparenciacatalunya.cat/api/views/j6ii-t3w2/rows.csv?accessType=DOWNLOAD",
}
FORMATOS = {"csv", "zip"}


def descargar() -> dict:
    stats = {}
    with http_client() as client:
        for ccaa, (api, paquete) in CKAN.items():
            try:
                resp = client.get(api, params={"id": paquete}, timeout=60)
                resp.raise_for_status()
                recursos = resp.json()["result"]["resources"]
            except Exception as exc:
                log.warning("%s: no se pudo resolver el dataset: %s", ccaa, exc)
                stats[ccaa] = f"error: {exc}"
                continue
            for r in recursos:
                if (r.get("format") or "").lower() not in FORMATOS:
                    continue
                nombre = r["url"].rsplit("/", 1)[1] or f"{r['id']}.{r['format'].lower()}"
                try:
                    f = download(client, f"cee_{ccaa}", r["url"], nombre, {"recurso": r.get("name")})
                    stats[f"{ccaa}/{nombre}"] = f.path.stat().st_size
                except Exception as exc:
                    log.warning("%s %s: %s", ccaa, nombre, exc)
                    stats[f"{ccaa}/{nombre}"] = f"error: {exc}"
        for ccaa, url in DIRECTAS.items():
            try:
                f = download(client, f"cee_{ccaa}", url, f"cee_{ccaa}.csv")
                stats[ccaa] = f.path.stat().st_size
            except Exception as exc:
                log.warning("%s: %s", ccaa, exc)
                stats[ccaa] = f"error: {exc}"
    return stats
