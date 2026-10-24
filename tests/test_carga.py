"""Carga de una extracción ficticia en la base de datos (necesita `docker compose up`)."""

import hashlib

import psycopg

from tasacion.ingesta import carga
from tasacion.ingesta import esquema as e
from tasacion.store import DATABASE_URL


def _nulos(modelo, **valores):
    campos = {k: None for k in modelo.model_fields}
    return modelo(**(campos | valores))


def test_carga_tasacion_ficticia(tmp_path):
    pdf = tmp_path / "ficticia.pdf"
    pdf.write_bytes(b"%PDF-1.4 tasacion ficticia de prueba " + tmp_path.name.encode())
    testigo = _nulos(
        e.Testigo, orden=1, tipo_dato="oferta", fuente="fotocasa", codigo_postal="2800X",
        sup_construida=90, precio=450000, precio_unitario=5000, coef_homogeneizacion=0.97,
        precio_homogeneizado=4850, coeficientes=[e.Coeficiente(factor="planta", valor=0.97)],
    )
    finca = _nulos(
        e.Finca, orden=1, tipo="vivienda", es_principal=True, ref_catastral="0000000AA0000A0001AA",
        codigo_postal="28009", sup_adoptada=85, valor_unitario=4900, valor_finca=416500,
        lat=40.42, lon=-3.68, testigos=[testigo],
    )
    t = _nulos(
        e.TasacionExtraida, sociedad_nombre="Sociedad Ficticia de Tasación", sociedad_codigo_bde="9999",
        tecnico_nombre="  técnico   ficticio ", tecnico_num_colegiado="X-1", tecnico_colegio="COAM",
        metodo_principal="comparacion", valor_tasacion=416500, condicionantes=[], advertencias=[],
        fincas=[finca], avisos_extraccion=[],
        evidencias=[e.Evidencia(ruta="valor_tasacion", pagina=3, texto="VALOR DE TASACIÓN 416.500 €", confianza="alta")],
    )
    meta = {"modelo": "test", "version": "test", "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}

    tasacion_id = carga.cargar(pdf, t, meta, operacion_ref=f"TEST-{tmp_path.name}")

    with psycopg.connect(DATABASE_URL) as conn:
        fila = conn.execute(
            """
            SELECT t.estado, s.codigo_bde, tc.nombre_normalizado, f.codigo_postal, ST_Y(f.geom),
                   te.codigo_postal, tco.valor, ce.ruta
            FROM tasacion.tasacion t
            JOIN tasacion.sociedad s ON s.id = t.sociedad_id
            JOIN tasacion.tecnico tc ON tc.id = t.tecnico_id
            JOIN tasacion.finca f ON f.tasacion_id = t.id
            JOIN tasacion.testigo te ON te.finca_id = f.id
            JOIN tasacion.testigo_coeficiente tco ON tco.testigo_id = te.id
            JOIN tasacion.campo_extraido ce ON ce.tasacion_id = t.id
            WHERE t.id = %s
            """,
            (tasacion_id,),
        ).fetchone()
        # limpieza: la tasación arrastra fincas, testigos y campos por ON DELETE CASCADE
        conn.execute("DELETE FROM tasacion.tasacion WHERE id = %s", (tasacion_id,))
        conn.execute("DELETE FROM ingest.raw_file WHERE source = 'cliente' AND sha256 = %s", (meta["sha256"],))
        conn.execute("DELETE FROM tasacion.operacion WHERE ref_cliente = %s", (f"TEST-{tmp_path.name}",))
        conn.execute("DELETE FROM tasacion.sociedad WHERE codigo_bde = '9999'")
        conn.execute("DELETE FROM tasacion.tecnico WHERE colegio = 'COAM' AND num_colegiado = 'X-1'")

    assert fila[0] == "extraida"
    assert fila[1] == "9999"
    assert fila[2] == "TÉCNICO FICTICIO"
    assert fila[3] == "28009"
    assert abs(fila[4] - 40.42) < 1e-9
    assert fila[5] is None  # CP mal formado del testigo -> null
    assert float(fila[6]) == 0.97
    assert fila[7] == "/valor_tasacion"
