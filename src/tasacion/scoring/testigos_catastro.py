"""Contraste de cada testigo con los inmuebles de su parcela catastral.

Un testigo real tiene que caber en el edificio donde se ha geolocalizado: un inmueble del uso
correspondiente en esa planta, con una superficie y un año parecidos. Si en la parcela no hay
ninguno así, el testigo está mal descrito, mal situado o es inventado.

Catastro da la superficie construida con comunes y los anuncios suelen dar la construida sin
ellos, de ahí la tolerancia amplia. En garajes y trasteros no se compara superficie: los
anuncios dan la útil de la plaza y Catastro la de la plaza con su parte de calle.
"""

import json
import logging
import re
from collections import Counter

import psycopg
from psycopg.rows import dict_row

from tasacion.fuentes import catastro_ovc
from tasacion.store import DATABASE_URL

log = logging.getLogger(__name__)

VERSION = "testigo-catastro-v1"
TOLERANCIA_SUP = 0.25
TOLERANCIA_ANIO = 5
USO = {"vivienda": "Residencial", "garaje": "Almacen-Estacionamiento",
       "trastero": "Almacen-Estacionamiento", "local": "Comercial"}


def planta(texto) -> int | None:
    """Planta como número: «9» -> 9, «sótano -1» -> -1, «bajo» / «00» / «BJ» -> 0; None si no se sabe."""
    t = str(texto or "").strip().lower()
    if not t:
        return None
    if m := re.search(r"-?\d+", t):
        n = int(m.group())
        return -abs(n) if "sót" in t or "sot" in t else n
    if t.startswith(("baj", "bj")):
        return 0
    if t.startswith(("sót", "sot", "sm", "st")):
        return -1
    return None


def contrastar(testigo: dict, tipo_finca: str, unidades: list[dict]) -> tuple[str, list[dict]]:
    """(resultado, diferencias) de un testigo frente a los inmuebles de su parcela."""
    if not unidades:
        return "no_encontrado", [{"campo": "parcela", "texto": "La parcela no tiene inmuebles en Catastro"}]
    uso = USO.get(tipo_finca)
    candidatas = [u for u in unidades if not uso or u["uso"] == uso]
    if not candidatas:
        usos = sorted({u["uso"] for u in unidades if u["uso"]})
        return "discrepante", [{"campo": "uso", "grave": True, "testigo": uso, "catastro": usos,
                                "texto": f"La parcela no tiene inmuebles de uso {uso} (sólo {', '.join(usos)})"}]
    diferencias = []

    # Una casa entera figura como planta «OD»/«TD»: ahí la planta del anuncio no se puede contrastar.
    p = planta(testigo.get("planta"))
    plantas = {planta(u["planta"]) for u in candidatas}
    if p is not None and None not in plantas:
        en_planta = [u for u in candidatas if planta(u["planta"]) == p]
        if en_planta:
            candidatas = en_planta
        else:
            diferencias.append({"campo": "planta", "grave": True, "testigo": p, "catastro": sorted(plantas),
                                "texto": f"No hay inmuebles de uso {uso} en la planta {p} "
                                         f"(plantas en Catastro: {min(plantas)} a {max(plantas)})"})

    sup = testigo.get("sup_construida")
    if tipo_finca == "vivienda" and sup:
        sup = float(sup)
        mejor = min((u for u in candidatas if u["sup"]), key=lambda u: abs(sup / u["sup"] - 1), default=None)
        if mejor and abs(sup / mejor["sup"] - 1) > TOLERANCIA_SUP:
            diferencias.append({"campo": "superficie", "testigo": sup, "catastro": mejor["sup"],
                                "texto": f"{sup:g} m² en el testigo; el inmueble más parecido de la parcela "
                                         f"tiene {mejor['sup']:g} m² ({sup / mejor['sup'] - 1:+.0%})"})

    anio = testigo.get("anio_construccion")
    anios = Counter(u["anio"] for u in candidatas if u["anio"])
    if anio and anios:
        catastral = anios.most_common(1)[0][0]
        if abs(anio - catastral) > TOLERANCIA_ANIO:
            diferencias.append({"campo": "anio", "testigo": anio, "catastro": catastral,
                                "texto": f"Año {anio} en el testigo frente a {catastral} en Catastro"})
    return ("discrepante" if diferencias else "coherente"), diferencias


def verificar(tasacion_id: int) -> list[dict]:
    """Contrasta los testigos con parcela conocida y guarda el resultado en scoring.verificacion_testigo."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        testigos = conn.execute(
            """
            SELECT t.id, t.orden, t.planta, t.sup_construida, t.anio_construccion, f.tipo AS tipo_finca,
                   COALESCE(left(t.ref_catastral, 14), t.ref_catastral_14_geo) AS rc14
            FROM tasacion.testigo t JOIN tasacion.finca f ON f.id = t.finca_id
            WHERE f.tasacion_id = %s ORDER BY f.orden, t.orden
            """, (tasacion_id,),
        ).fetchall()
    out = []
    for t in testigos:
        if not t["rc14"]:
            res, dif = "no_evaluable", [{"campo": "parcela", "texto": "Testigo sin parcela catastral conocida"}]
        else:
            res, dif = contrastar(t, t["tipo_finca"], catastro_ovc.inmuebles_parcela(t["rc14"]))
        out.append({"testigo_id": t["id"], "orden": t["orden"], "rc14": t["rc14"], "resultado": res,
                    "diferencias": dif})
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("DELETE FROM scoring.verificacion_testigo WHERE version = %s AND testigo_id = ANY(%s)",
                     (VERSION, [t["id"] for t in testigos]))
        for v in out:
            conn.execute(
                "INSERT INTO scoring.verificacion_testigo (testigo_id, resultado, diferencias, version) "
                "VALUES (%s, %s, %s, %s)",
                (v["testigo_id"], v["resultado"], json.dumps({"rc14": v["rc14"], "diferencias": v["diferencias"]},
                                                              ensure_ascii=False), VERSION),
            )
    return out
