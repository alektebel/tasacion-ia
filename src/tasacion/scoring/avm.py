"""AVM v1 por comparables: distribución de €/m² de anuncios cercanos y similares.

- Candidatos: anuncios activos con coordenadas a <= RADIO_MAX_M, ampliando el radio desde
  RADIO_INICIAL_M hasta reunir MIN_COMPARABLES.
- Peso de cada comparable: decae con la distancia y con la diferencia relativa de superficie.
- Salida: percentiles ponderados P10/P50/P90 de €/m² de *oferta* y valor = €/m² x superficie
  x factor de negociación.

El factor de negociación (oferta -> cierre) es un parámetro: comparar Registradores con los
anuncios por provincia no da un descuento coherente (superficies y mezclas distintas), así que
se calibrará con el histórico del banco (precio de compraventa real frente a este AVM).
"""

import json
import math
from dataclasses import asdict, dataclass

import psycopg

from tasacion.store import DATABASE_URL

MODELO = "comparables"
VERSION = "avm-v1"
RADIO_INICIAL_M = 300
RADIO_MAX_M = 3000
MIN_COMPARABLES = 15
MAX_COMPARABLES = 60
ESCALA_DISTANCIA_M = 500
ESCALA_SUPERFICIE = 0.3      # en log: 0.3 ~ ±35 % de superficie
FACTOR_NEGOCIACION = 0.92    # provisional, ver docstring
EUR_M2_MIN, EUR_M2_MAX = 200, 30000

CANDIDATOS_SQL = """
SELECT a.id, a.portal, ST_Distance(a.geom::geography, p.pt::geography) AS d,
       a.sup_construida, o.precio, o.precio / a.sup_construida AS eur_m2
FROM fuente.anuncio a
CROSS JOIN (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326) AS pt) p
JOIN LATERAL (
    SELECT precio FROM fuente.anuncio_observacion o
    WHERE o.anuncio_id = a.id ORDER BY observado_en DESC LIMIT 1
) o ON true
WHERE a.activo AND a.operacion = 'venta' AND a.geom IS NOT NULL
  AND ST_DWithin(a.geom, p.pt, %(grados)s)
  AND ST_DWithin(a.geom::geography, p.pt::geography, %(radio)s)
  AND a.sup_construida BETWEEN %(sup)s * 0.5 AND %(sup)s * 2
  AND o.precio / a.sup_construida BETWEEN %(min)s AND %(max)s
  AND coalesce(a.tipologia, '') NOT ILIKE '%%rustic%%'
"""


@dataclass
class Estimacion:
    eur_m2_p10: float
    eur_m2_p50: float
    eur_m2_p90: float
    valor_p10: float
    valor_p50: float
    valor_p90: float
    n_comparables: int
    radio_m: int
    factor_negociacion: float
    comparables: list[dict]


def _percentil_ponderado(valores: list[tuple[float, float]], q: float) -> float:
    """valores = [(x, peso)] -> percentil q (0-1) por interpolación de la CDF ponderada."""
    valores = sorted(valores)
    total = sum(w for _, w in valores)
    acumulado = 0.0
    for x, w in valores:
        acumulado += w
        if acumulado >= q * total:
            return x
    return valores[-1][0]


def estimar(
    lat: float, lon: float, sup: float, factor_negociacion: float = FACTOR_NEGOCIACION,
    conn: psycopg.Connection | None = None,
) -> Estimacion | None:
    propia = conn is None
    conn = conn or psycopg.connect(DATABASE_URL)
    try:
        radio = RADIO_INICIAL_M
        while True:
            filas = conn.execute(
                CANDIDATOS_SQL,
                {"lat": lat, "lon": lon, "sup": sup, "radio": radio,
                 "grados": radio / 111_000 / max(math.cos(math.radians(lat)), 0.1),
                 "min": EUR_M2_MIN, "max": EUR_M2_MAX},
            ).fetchall()
            if len(filas) >= MIN_COMPARABLES or radio >= RADIO_MAX_M:
                break
            radio = min(radio * 2, RADIO_MAX_M)
    finally:
        if propia:
            conn.close()
    if len(filas) < 5:
        return None

    comparables = []
    for anuncio_id, portal, d, sup_c, precio, eur_m2 in filas:
        peso = math.exp(-d / ESCALA_DISTANCIA_M) * math.exp(-abs(math.log(float(sup_c) / sup)) / ESCALA_SUPERFICIE)
        comparables.append({"anuncio_id": anuncio_id, "portal": portal, "distancia_m": round(d, 1),
                            "sup": float(sup_c), "precio": float(precio), "eur_m2": float(eur_m2), "peso": peso})
    comparables.sort(key=lambda c: -c["peso"])
    comparables = comparables[:MAX_COMPARABLES]

    # Recorte de atípicos: fuera de P5-P95 ponderado.
    pares = [(c["eur_m2"], c["peso"]) for c in comparables]
    lo, hi = _percentil_ponderado(pares, 0.05), _percentil_ponderado(pares, 0.95)
    comparables = [c for c in comparables if lo <= c["eur_m2"] <= hi]
    pares = [(c["eur_m2"], c["peso"]) for c in comparables]

    p10, p50, p90 = (_percentil_ponderado(pares, q) for q in (0.1, 0.5, 0.9))
    f = factor_negociacion * sup
    return Estimacion(
        eur_m2_p10=round(p10, 2), eur_m2_p50=round(p50, 2), eur_m2_p90=round(p90, 2),
        valor_p10=round(p10 * f, 2), valor_p50=round(p50 * f, 2), valor_p90=round(p90 * f, 2),
        n_comparables=len(comparables), radio_m=radio, factor_negociacion=factor_negociacion,
        comparables=comparables,
    )


def estimar_finca(finca_id: int) -> int | None:
    """Estima una finca de tasacion.finca y guarda el resultado en scoring.avm_estimacion."""
    with psycopg.connect(DATABASE_URL) as conn:
        fila = conn.execute(
            "SELECT ST_Y(geom), ST_X(geom), coalesce(sup_adoptada, sup_construida_comprobada, sup_util_comprobada), "
            "t.fecha_emision FROM tasacion.finca f JOIN tasacion.tasacion t ON t.id = f.tasacion_id WHERE f.id = %s",
            (finca_id,),
        ).fetchone()
        if not fila or fila[0] is None or not fila[2]:
            return None
        lat, lon, sup, fecha = fila
        est = estimar(lat, lon, float(sup), conn=conn)
        if est is None:
            return None
        detalle = {k: v for k, v in asdict(est).items() if k not in ("comparables",)}
        est_id = conn.execute(
            """
            INSERT INTO scoring.avm_estimacion
                (finca_id, modelo, modelo_version, fecha_valor, eur_m2_p10, eur_m2_p50, eur_m2_p90,
                 valor_p10, valor_p50, valor_p90, descuento_oferta_cierre, n_comparables, detalle)
            VALUES (%s, %s, %s, coalesce(%s, current_date), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (finca_id, MODELO, VERSION, fecha, est.eur_m2_p10, est.eur_m2_p50, est.eur_m2_p90,
             est.valor_p10, est.valor_p50, est.valor_p90, 1 - est.factor_negociacion,
             est.n_comparables, json.dumps(detalle)),
        ).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO scoring.avm_comparable (estimacion_id, anuncio_id, distancia_m, similitud, precio_ajustado, peso) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(est_id, c["anuncio_id"], c["distancia_m"], c["peso"], c["eur_m2"] * est.factor_negociacion, c["peso"])
                 for c in est.comparables],
            )
        return est_id
