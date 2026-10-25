"""Índice de Precios de Vivienda (INE, tabla 80270, base 2025): llevar un €/m² de hoy a otra fecha."""

import json
from datetime import date
from functools import cache
from pathlib import Path

import psycopg

from tasacion.store import DATABASE_URL

# Código INE de provincia -> nombre de la CCAA tal como aparece en las series del INE.
CCAA = {
    **dict.fromkeys([4, 11, 14, 18, 21, 23, 29, 41], "Andalucía"),
    **dict.fromkeys([22, 44, 50], "Aragón"),
    33: "Asturias, Principado de", 7: "Balears, Illes",
    **dict.fromkeys([35, 38], "Canarias"), 39: "Cantabria",
    **dict.fromkeys([5, 9, 24, 34, 37, 40, 42, 47, 49], "Castilla y León"),
    **dict.fromkeys([2, 13, 16, 19, 45], "Castilla - La Mancha"),
    **dict.fromkeys([8, 17, 25, 43], "Cataluña"),
    **dict.fromkeys([3, 12, 46], "Comunitat Valenciana"),
    **dict.fromkeys([6, 10], "Extremadura"),
    **dict.fromkeys([15, 27, 32, 36], "Galicia"),
    28: "Madrid, Comunidad de", 30: "Murcia, Región de", 31: "Navarra, Comunidad Foral de",
    **dict.fromkeys([1, 20, 48], "País Vasco"), 26: "Rioja, La", 51: "Ceuta", 52: "Melilla",
}
TRIMESTRE = {19: 1, 20: 2, 21: 3, 22: 4}  # FK_Periodo del INE


@cache
def _serie(region: str) -> dict[tuple[int, int], float]:
    with psycopg.connect(DATABASE_URL) as conn:
        ruta = conn.execute(
            "SELECT storage_uri FROM ingest.raw_file WHERE source = 'ine' AND storage_uri LIKE '%%ine_80270_%%' "
            "ORDER BY fetched_at DESC LIMIT 1"
        ).fetchone()[0]
    for s in json.loads(Path(ruta).read_text()):
        if s["Nombre"].strip() == f"{region}. Vivienda segunda mano. Índice.":
            return {(d["Anyo"], TRIMESTRE[d["FK_Periodo"]]): d["Valor"] for d in s["Data"] if d["Valor"]}
    raise KeyError(region)


def factor(provincia_ine: int | None, desde: date) -> float:
    """Multiplicador para pasar un precio actual (último trimestre publicado) a la fecha `desde`."""
    serie = _serie(CCAA.get(provincia_ine, "Nacional"))
    ultimo = max(serie)
    clave = (desde.year, (desde.month - 1) // 3 + 1)
    # Si la fecha es posterior al último dato, no hay ajuste; si es anterior al primero, el primero.
    clave = min(max(clave, min(serie)), ultimo)
    return serie[clave] / serie[ultimo]
