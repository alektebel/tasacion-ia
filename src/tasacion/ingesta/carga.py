"""Carga de una TasacionExtraida en tasacion.* (más ingest.raw_file para el PDF)."""

import json
import re
from pathlib import Path

import psycopg

from tasacion.ingesta.esquema import TasacionExtraida
from tasacion.store import DATABASE_URL, register

FINCA_COLUMNAS = [
    "orden", "tipo", "es_principal", "ref_catastral", "finca_registral", "registro_propiedad",
    "tomo", "libro", "folio", "idufir", "direccion", "tipo_via", "nombre_via", "numero",
    "escalera", "planta", "puerta", "codigo_postal", "municipio", "provincia",
    "sup_util_comprobada", "sup_construida_comprobada", "sup_construida_con_comunes",
    "sup_util_registral", "sup_construida_registral", "sup_catastral", "sup_adoptada",
    "sup_parcela", "anio_construccion", "anio_rehabilitacion", "dormitorios", "banos",
    "ascensor", "exterior", "orientacion", "estado_conservacion", "calidad_constructiva",
    "certificado_energetico", "ocupacion", "proteccion_publica", "valor_unitario", "valor_finca",
]
TESTIGO_COLUMNAS = [
    "orden", "tipo_dato", "fuente", "url", "ref_anuncio", "telefono_contacto", "fecha_dato",
    "direccion", "codigo_postal", "ref_catastral", "planta", "sup_construida", "sup_util",
    "dormitorios", "banos", "anio_construccion", "estado_conservacion", "precio",
    "precio_unitario", "coef_homogeneizacion", "precio_homogeneizado", "peso",
]
# Postgres rechaza en char(5) un CP mal extraído; mejor null que abortar la carga.
_CP = re.compile(r"^\d{5}$")


def _cp(valor: str | None) -> str | None:
    return valor if valor and _CP.match(valor) else None


def _normaliza_nombre(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre).strip().upper()


def _sociedad(conn: psycopg.Connection, t: TasacionExtraida) -> int | None:
    if not (t.sociedad_nombre or t.sociedad_codigo_bde or t.sociedad_cif):
        return None
    for col, val in (("codigo_bde", t.sociedad_codigo_bde), ("cif", t.sociedad_cif)):
        if val:
            row = conn.execute(f"SELECT id FROM tasacion.sociedad WHERE {col} = %s", (val,)).fetchone()
            if row:
                return row[0]
    if t.sociedad_nombre:
        row = conn.execute(
            "SELECT id FROM tasacion.sociedad WHERE upper(nombre) = %s", (_normaliza_nombre(t.sociedad_nombre),)
        ).fetchone()
        if row:
            return row[0]
    return conn.execute(
        "INSERT INTO tasacion.sociedad (nombre, codigo_bde, cif) VALUES (%s, %s, %s) RETURNING id",
        (t.sociedad_nombre or t.sociedad_codigo_bde or t.sociedad_cif, t.sociedad_codigo_bde, t.sociedad_cif),
    ).fetchone()[0]


def _tecnico(conn: psycopg.Connection, t: TasacionExtraida) -> int | None:
    if not t.tecnico_nombre:
        return None
    nombre = _normaliza_nombre(t.tecnico_nombre)
    if t.tecnico_num_colegiado:
        row = conn.execute(
            """
            INSERT INTO tasacion.tecnico (nombre_normalizado, num_colegiado, colegio, titulacion)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (colegio, num_colegiado) DO UPDATE SET titulacion = COALESCE(tasacion.tecnico.titulacion, EXCLUDED.titulacion)
            RETURNING id
            """,
            (nombre, t.tecnico_num_colegiado, t.tecnico_colegio, t.tecnico_titulacion),
        ).fetchone()
        tecnico_id = row[0]
    else:
        # Sin nº de colegiado sólo podemos casar por alias exacto.
        row = conn.execute("SELECT tecnico_id FROM tasacion.tecnico_alias WHERE alias = %s", (nombre,)).fetchone()
        tecnico_id = row[0] if row else conn.execute(
            "INSERT INTO tasacion.tecnico (nombre_normalizado, titulacion) VALUES (%s, %s) RETURNING id",
            (nombre, t.tecnico_titulacion),
        ).fetchone()[0]
    conn.execute(
        "INSERT INTO tasacion.tecnico_alias (tecnico_id, alias) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (tecnico_id, nombre),
    )
    return tecnico_id


def cargar(pdf: Path, t: TasacionExtraida, meta: dict, operacion_ref: str | None = None) -> int:
    """Inserta la tasación y devuelve su id."""
    raw = register("cliente", pdf, meta["sha256"], None, "application/pdf", {"nombre": pdf.name})
    with psycopg.connect(DATABASE_URL) as conn, conn.transaction():
        operacion_id = None
        if operacion_ref:
            operacion_id = conn.execute(
                "INSERT INTO tasacion.operacion (ref_cliente) VALUES (%s) "
                "ON CONFLICT (ref_cliente) DO UPDATE SET ref_cliente = EXCLUDED.ref_cliente RETURNING id",
                (operacion_ref,),
            ).fetchone()[0]
        tasacion_id = conn.execute(
            """
            INSERT INTO tasacion.tasacion
                (raw_file_id, operacion_id, sociedad_id, tecnico_id, num_informe, finalidad,
                 fecha_visita, fecha_emision, fecha_caducidad, metodo_principal, valor_tasacion,
                 valor_mercado, valor_hipotecario, valor_reposicion_bruto, valor_reposicion_neto,
                 valor_seguro, condicionantes, advertencias, estado, extraccion_modelo,
                 extraccion_version, extraccion_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'extraida', %s, %s, %s)
            RETURNING id
            """,
            (
                raw.raw_file_id, operacion_id, _sociedad(conn, t), _tecnico(conn, t), t.num_informe,
                t.finalidad, t.fecha_visita, t.fecha_emision, t.fecha_caducidad, t.metodo_principal,
                t.valor_tasacion, t.valor_mercado, t.valor_hipotecario, t.valor_reposicion_bruto,
                t.valor_reposicion_neto, t.valor_seguro, t.condicionantes, t.advertencias,
                meta["modelo"], meta["version"], t.model_dump_json(),
            ),
        ).fetchone()[0]

        for finca in t.fincas:
            valores = finca.model_dump()
            valores["codigo_postal"] = _cp(finca.codigo_postal)
            cols = ", ".join(FINCA_COLUMNAS)
            marcas = ", ".join(["%s"] * len(FINCA_COLUMNAS))
            finca_id = conn.execute(
                f"""
                INSERT INTO tasacion.finca (tasacion_id, {cols}, geom, geocodificacion_fuente)
                VALUES (%s, {marcas},
                        CASE WHEN %s::float IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                        CASE WHEN %s::float IS NULL THEN NULL ELSE 'informe' END)
                RETURNING id
                """,
                [tasacion_id, *[valores[c] for c in FINCA_COLUMNAS],
                 finca.lat, finca.lon, finca.lat, finca.lat],
            ).fetchone()[0]
            for testigo in finca.testigos:
                tv = testigo.model_dump()
                tv["codigo_postal"] = _cp(testigo.codigo_postal)
                cols = ", ".join(TESTIGO_COLUMNAS)
                marcas = ", ".join(["%s"] * len(TESTIGO_COLUMNAS))
                testigo_id = conn.execute(
                    f"INSERT INTO tasacion.testigo (finca_id, {cols}) VALUES (%s, {marcas}) RETURNING id",
                    [finca_id, *[tv[c] for c in TESTIGO_COLUMNAS]],
                ).fetchone()[0]
                for c in testigo.coeficientes:
                    conn.execute(
                        "INSERT INTO tasacion.testigo_coeficiente (testigo_id, factor, valor) VALUES (%s, %s, %s) "
                        "ON CONFLICT DO NOTHING",
                        (testigo_id, c.factor, c.valor),
                    )

        for e in t.evidencias:
            conn.execute(
                """
                INSERT INTO tasacion.campo_extraido (tasacion_id, ruta, pagina, texto_origen, confianza, metodo)
                VALUES (%s, %s, %s, %s, %s, 'llm') ON CONFLICT (tasacion_id, ruta) DO NOTHING
                """,
                (tasacion_id, "/" + e.ruta.lstrip("/"), e.pagina, e.texto,
                 {"alta": 0.9, "media": 0.6, "baja": 0.3}[e.confianza]),
            )
        # Si hay evidencias de baja confianza o avisos, la extracción pasa por revisión humana.
        if t.avisos_extraccion or any(e.confianza == "baja" for e in t.evidencias):
            conn.execute(
                "UPDATE tasacion.tasacion SET estado = 'en_revision_extraccion' WHERE id = %s", (tasacion_id,)
            )
        conn.execute(
            "UPDATE tasacion.tasacion SET extraccion_json = extraccion_json || %s::jsonb WHERE id = %s",
            (json.dumps({"_meta": meta}), tasacion_id),
        )
    return tasacion_id
