"""Reglas de validación de una tasación y veredicto (semáforo).

Cada regla devuelve un Chequeo con resultado ok / aviso / fallo / no_evaluable, una severidad
0-1 que resta del sub-score de su categoría y la evidencia que lo justifica. El veredicto:

- revision_obligatoria: algún fallo de una regla bloqueante, o algún sub-score < UMBRAL_ROJO
- dudas:                algún fallo, o algún sub-score < UMBRAL_AMARILLO
- validada:             el resto

Los umbrales son provisionales hasta calibrarlos con las revisiones del tasador senior.
"""

import json
import logging
import statistics
from dataclasses import dataclass, field
from datetime import date

import psycopg
from psycopg.rows import dict_row

from tasacion.fuentes import catastro_ovc
from tasacion.scoring import avm, ipv
from tasacion.store import DATABASE_URL

log = logging.getLogger(__name__)

VERSION = "reglas-v1"
UMBRAL_ROJO = 0.5
UMBRAL_AMARILLO = 0.8
MIN_TESTIGOS = 6                 # ECO/805: mínimo de comparables para el método de comparación
VALIDEZ_MAX_DIAS = 183           # validez de 6 meses del certificado


@dataclass
class Chequeo:
    codigo: str
    categoria: str               # valor | calidad | fraude
    resultado: str               # ok | aviso | fallo | no_evaluable
    explicacion: str
    severidad: float = 0.0
    bloqueante: bool = False
    observado: object = None
    esperado: object = None
    evidencia: dict = field(default_factory=dict)


def _desvio(a: float, b: float) -> float:
    return float(a) / float(b) - 1


# ---------------------------------------------------------------------------
# reglas sobre la finca principal frente a Catastro
# ---------------------------------------------------------------------------

def r_catastro(finca: dict) -> list[Chequeo]:
    rc = finca.get("ref_catastral")
    if not rc or len(rc.replace(" ", "")) != 20:
        return [Chequeo("RC_PRESENTE", "calidad", "fallo", "El informe no trae una referencia catastral de 20 caracteres",
                        0.4, observado=rc)]
    cat = catastro_ovc.inmueble(rc)
    if not cat:
        return [Chequeo("RC_EXISTE", "calidad", "fallo", f"La referencia catastral {rc} no existe en Catastro",
                        1.0, bloqueante=True, observado=rc)]
    out = [Chequeo("RC_EXISTE", "calidad", "ok", "La referencia catastral existe en Catastro", evidencia={"catastro": cat})]

    uso = (cat.get("uso") or "").lower()
    if finca["tipo"] == "vivienda" and uso and "residencial" not in uso:
        out.append(Chequeo("USO_CATASTRO", "calidad", "fallo", f"Catastro registra uso «{cat['uso']}», no residencial",
                           0.5, bloqueante=True, observado="vivienda", esperado=cat["uso"]))

    # Catastro da superficie construida con comunes: se compara con la equivalente del informe.
    sup_inf = finca.get("sup_construida_con_comunes") or finca.get("sup_adoptada")
    if sup_inf and cat.get("sup"):
        d = _desvio(sup_inf, cat["sup"])
        res, sev, bloq = ("ok", 0.0, False)
        if abs(d) > 0.20:
            res, sev, bloq = ("fallo", 0.6, True)
        elif abs(d) > 0.10:
            res, sev = ("aviso", 0.3)
        out.append(Chequeo("SUP_CATASTRO", "calidad", res,
                           f"Superficie del informe {sup_inf} m² frente a {cat['sup']} m² en Catastro ({d:+.0%})",
                           sev, bloq, sup_inf, cat["sup"], {"desvio": d}))
    # La superficie adoptada para valorar mayor que la catastral infla el valor.
    if finca.get("sup_adoptada") and cat.get("sup") and _desvio(finca["sup_adoptada"], cat["sup"]) > 0.10:
        d = _desvio(finca["sup_adoptada"], cat["sup"])
        out.append(Chequeo("SUP_ADOPTADA_MAYOR", "fraude", "aviso",
                           f"La superficie adoptada ({finca['sup_adoptada']} m²) supera la catastral en {d:.0%}",
                           min(0.5, d), observado=finca["sup_adoptada"], esperado=cat["sup"]))

    if finca.get("anio_construccion") and cat.get("anio"):
        dif = finca["anio_construccion"] - cat["anio"]
        res, sev = ("ok", 0.0) if abs(dif) <= 5 else ("aviso", 0.2)
        out.append(Chequeo("ANIO_CATASTRO", "calidad", res,
                           f"Año de construcción {finca['anio_construccion']} frente a {cat['anio']} en Catastro",
                           sev, observado=finca["anio_construccion"], esperado=cat["anio"]))

    if finca.get("codigo_postal") and cat.get("codigo_postal") and finca["codigo_postal"] != cat["codigo_postal"]:
        out.append(Chequeo("CP_CATASTRO", "calidad", "aviso",
                           f"CP {finca['codigo_postal']} frente a {cat['codigo_postal']} en Catastro",
                           0.1, observado=finca["codigo_postal"], esperado=cat["codigo_postal"]))
    return out


# ---------------------------------------------------------------------------
# reglas sobre testigos y homogeneización
# ---------------------------------------------------------------------------

def r_testigos(finca: dict, testigos: list[dict], metodo: str | None, emision: date | None = None) -> list[Chequeo]:
    out = []
    if metodo not in (None, "comparacion"):
        return out
    n = len(testigos)
    out.append(Chequeo("MIN_TESTIGOS", "calidad", "ok" if n >= MIN_TESTIGOS else "fallo",
                       f"{n} testigos (mínimo {MIN_TESTIGOS})", 0.0 if n >= MIN_TESTIGOS else 0.5,
                       observado=n, esperado=MIN_TESTIGOS))
    if not testigos:
        return out

    # Testigos distintos con precio y superficie idénticos: posible copia o invención.
    vistos: dict[tuple, list[int]] = {}
    for t in testigos:
        if t["precio"] and t["sup_construida"]:
            vistos.setdefault((round(float(t["precio"])), round(float(t["sup_construida"]))), []).append(t["orden"])
    duplicados = [ordenes for ordenes in vistos.values() if len(ordenes) > 1]
    if duplicados:
        out.append(Chequeo("TESTIGOS_IDENTICOS", "fraude", "fallo" if len(duplicados) > 1 else "aviso",
                           f"Testigos con precio y superficie idénticos: {duplicados}",
                           min(1.0, 0.4 * len(duplicados)), observado=duplicados))

    # Un testigo fechado después de emitir el informe no pudo usarse para valorar.
    if emision:
        posteriores = [t["orden"] for t in testigos if t["fecha_dato"] and t["fecha_dato"] > emision]
        if posteriores:
            out.append(Chequeo("TESTIGOS_POSTERIORES", "fraude", "fallo",
                               f"Testigos fechados después de la emisión del informe ({emision}): {posteriores}",
                               min(1.0, 0.3 * len(posteriores)), bloqueante=True, observado=posteriores))

    sin_fuente = [t["orden"] for t in testigos if not (t["url"] or t["fuente"])]
    out.append(Chequeo("TESTIGOS_TRAZABLES", "calidad", "aviso" if sin_fuente else "ok",
                       "Todos los testigos indican su fuente" if not sin_fuente
                       else f"Testigos sin fuente ni URL (exigible desde la ECM/599/2025): {sin_fuente}",
                       0.1 * len(sin_fuente), observado=sin_fuente))

    extremos = [t["orden"] for t in testigos
                if t["coef_homogeneizacion"] and not 0.7 <= float(t["coef_homogeneizacion"]) <= 1.3]
    if extremos:
        out.append(Chequeo("HOMOG_EXTREMA", "calidad", "aviso",
                           f"Coeficientes de homogeneización fuera de [0,7-1,3] en testigos {extremos}",
                           0.2, observado=extremos))

    # Sesgo de la homogeneización: si casi todo empuja al alza, el valor sube artificialmente.
    coefs = [float(t["coef_homogeneizacion"]) for t in testigos if t["coef_homogeneizacion"]]
    if len(coefs) >= 4 and statistics.mean(coefs) > 1.10:
        out.append(Chequeo("HOMOG_AL_ALZA", "fraude", "aviso",
                           f"La homogeneización media sube el precio de los testigos un {statistics.mean(coefs) - 1:.0%}",
                           0.3, observado=statistics.mean(coefs)))

    homog = [float(t["precio_homogeneizado"]) for t in testigos if t["precio_homogeneizado"]]
    if homog and finca.get("valor_unitario"):
        media = statistics.mean(homog)
        d = _desvio(finca["valor_unitario"], media)
        res, sev = ("ok", 0.0) if abs(d) <= 0.05 else ("aviso", min(0.5, abs(d)))
        out.append(Chequeo("VALOR_VS_TESTIGOS", "calidad", res,
                           f"Valor unitario adoptado {finca['valor_unitario']} €/m² frente a media homogeneizada "
                           f"{media:.0f} €/m² ({d:+.1%})", sev, observado=finca["valor_unitario"], esperado=round(media, 2)))
    return out


# ---------------------------------------------------------------------------
# valor frente al AVM
# ---------------------------------------------------------------------------

def r_avm(finca: dict, fecha: date | None) -> list[Chequeo]:
    if finca.get("lat") is None:
        return [Chequeo("VALOR_AVM", "valor", "no_evaluable", "Finca sin coordenadas")]
    sup = finca.get("sup_adoptada") or finca.get("sup_construida_comprobada")
    if not (sup and finca.get("valor_unitario")):
        return [Chequeo("VALOR_AVM", "valor", "no_evaluable", "Falta superficie o valor unitario")]
    est = avm.estimar(finca["lat"], finca["lon"], float(sup))
    if est is None:
        return [Chequeo("VALOR_AVM", "valor", "no_evaluable", "Sin comparables suficientes alrededor")]
    prov = int(finca["codigo_postal"][:2]) if finca.get("codigo_postal") else None
    f = ipv.factor(prov, fecha or date.today()) * est.factor_negociacion
    p10, p50, p90 = est.eur_m2_p10 * f, est.eur_m2_p50 * f, est.eur_m2_p90 * f
    v = float(finca["valor_unitario"])
    d = v / p50 - 1
    if v > p90 * 1.15:
        res, sev, bloq = "fallo", min(1.0, d), True
    elif v > p90:
        res, sev, bloq = "aviso", 0.4, False
    elif v < p10:
        res, sev, bloq = "aviso", 0.2, False
    else:
        res, sev, bloq = "ok", 0.0, False
    return [Chequeo("VALOR_AVM", "valor", res,
                    f"{v:.0f} €/m² frente a AVM P10-P50-P90 {p10:.0f}-{p50:.0f}-{p90:.0f} €/m² "
                    f"a fecha de la tasación ({d:+.0%} sobre la mediana; {est.n_comparables} comparables en {est.radio_m} m)",
                    sev, bloq, v, {"p10": round(p10), "p50": round(p50), "p90": round(p90)},
                    {"factor_ipv": round(f / est.factor_negociacion, 4), "factor_negociacion": est.factor_negociacion,
                     "comparables": [c["anuncio_id"] for c in est.comparables[:20]]})]


# ---------------------------------------------------------------------------
# reglas sobre el informe
# ---------------------------------------------------------------------------

def r_informe(t: dict) -> list[Chequeo]:
    out = []
    if t["fecha_emision"] and t["fecha_caducidad"]:
        dias = (t["fecha_caducidad"] - t["fecha_emision"]).days
        if dias > VALIDEZ_MAX_DIAS:
            out.append(Chequeo("VALIDEZ", "calidad", "aviso",
                               f"Validez declarada de {dias} días (la ECO/805 fija 6 meses)", 0.1, observado=dias))
    avisos = [a for a in (t["extraccion_json"] or {}).get("avisos_extraccion") or [] if isinstance(a, dict)]
    peso = {"alta": 0.25, "media": 0.08, "baja": 0.02}
    for tipo, codigo, texto in (("contradiccion", "CONTRADICCIONES_INFORME", "contradicciones internas"),
                                ("laguna", "LAGUNAS_INFORME", "lagunas frente a la ECO/805")):
        lista = [a for a in avisos if a["tipo"] == tipo]
        if not lista:
            continue
        graves = [a for a in lista if a["gravedad"] == "alta"]
        out.append(Chequeo(codigo, "calidad", "fallo" if graves else "aviso",
                           f"{len(lista)} {texto} ({len(graves)} graves)"
                           + (f"; la más grave: {graves[0]['texto'][:200]}" if graves else ""),
                           min(0.6, sum(peso[a["gravedad"]] for a in lista)), observado=lista))
    return out


def r_alcance(t: dict, finca: dict | None) -> list[Chequeo]:
    """El v1 sólo valida vivienda terminada por comparación; el resto se deriva a revisión."""
    if finca is None or finca["tipo"] != "vivienda" or t["metodo_principal"] not in (None, "comparacion"):
        return [Chequeo("ALCANCE", "calidad", "fallo",
                        f"Fuera del alcance del v1 (finca principal «{finca['tipo'] if finca else '-'}», "
                        f"método «{t['metodo_principal']}»): requiere revisión manual",
                        0.0, bloqueante=True)]
    return []


# ---------------------------------------------------------------------------
# orquestación
# ---------------------------------------------------------------------------

def puntuar(tasacion_id: int) -> dict:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        t = conn.execute("SELECT * FROM tasacion.tasacion WHERE id = %s", (tasacion_id,)).fetchone()
        finca = conn.execute(
            "SELECT *, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM tasacion.finca WHERE tasacion_id = %s "
            "ORDER BY es_principal DESC, orden LIMIT 1", (tasacion_id,)
        ).fetchone()
        testigos = conn.execute(
            "SELECT * FROM tasacion.testigo WHERE finca_id = %s ORDER BY orden", (finca["id"],)
        ).fetchall() if finca else []

    chequeos = r_informe(t) + r_alcance(t, finca)
    if finca and not any(c.codigo == "ALCANCE" for c in chequeos):
        # Geolocalizar la finca por su referencia catastral si el informe no trae coordenadas.
        if finca["lat"] is None and finca["ref_catastral"]:
            coords = catastro_ovc.coordenadas(finca["ref_catastral"])
            if coords:
                finca["lat"], finca["lon"] = coords
                with psycopg.connect(DATABASE_URL) as conn:
                    conn.execute(
                        "UPDATE tasacion.finca SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326), "
                        "geocodificacion_fuente = 'catastro' WHERE id = %s", (coords[1], coords[0], finca["id"]))
        chequeos += r_catastro(finca) + r_testigos(finca, testigos, t["metodo_principal"], t["fecha_emision"]) + r_avm(finca, t["fecha_emision"])

    sub = {}
    for cat in ("valor", "calidad", "fraude"):
        sub[cat] = max(0.0, 1 - sum(c.severidad for c in chequeos if c.categoria == cat and c.resultado in ("aviso", "fallo")))
    compuesto = 0.5 * sub["valor"] + 0.3 * sub["calidad"] + 0.2 * sub["fraude"]
    if any(c.bloqueante and c.resultado == "fallo" for c in chequeos) or min(sub.values()) < UMBRAL_ROJO:
        veredicto = "revision_obligatoria"
    elif any(c.resultado == "fallo" for c in chequeos) or min(sub.values()) < UMBRAL_AMARILLO:
        veredicto = "dudas"
    else:
        veredicto = "validada"

    with psycopg.connect(DATABASE_URL) as conn:
        ids = []
        for c in chequeos:
            ids.append(conn.execute(
                """
                INSERT INTO scoring.chequeo (tasacion_id, codigo, categoria, resultado, bloqueante, severidad,
                    valor_observado, valor_esperado, explicacion, evidencia, version_reglas)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (tasacion_id, c.codigo, c.categoria, c.resultado, c.bloqueante, c.severidad,
                 json.dumps(c.observado, default=str), json.dumps(c.esperado, default=str),
                 c.explicacion, json.dumps(c.evidencia, default=str), VERSION),
            ).fetchone()[0])
        motivos = sorted(
            ({"chequeo_id": i, "codigo": c.codigo, "resultado": c.resultado, "severidad": c.severidad,
              "explicacion": c.explicacion} for i, c in zip(ids, chequeos) if c.resultado in ("aviso", "fallo")),
            key=lambda m: (m["resultado"] != "fallo", -m["severidad"]),
        )
        conn.execute(
            "INSERT INTO scoring.score (tasacion_id, version, sub_valor, sub_calidad, sub_fraude, compuesto, veredicto, motivos) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (tasacion_id, VERSION, sub["valor"], sub["calidad"], sub["fraude"], compuesto, veredicto, json.dumps(motivos)),
        )
        conn.execute("UPDATE tasacion.tasacion SET estado = 'puntuada' WHERE id = %s", (tasacion_id,))
    return {"tasacion_id": tasacion_id, "veredicto": veredicto, "sub_scores": sub, "compuesto": round(compuesto, 3),
            "chequeos": [(c.codigo, c.resultado, c.explicacion) for c in chequeos]}
