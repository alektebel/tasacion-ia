"""Vista web contra la base de datos local (necesita `docker compose up` y alguna tasación cargada)."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from tasacion.store import DATABASE_URL
from tasacion.web.app import app

cliente = TestClient(app)


def _una_tasacion() -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        fila = conn.execute("SELECT tasacion_id FROM scoring.score ORDER BY created_at DESC LIMIT 1").fetchone()
    if not fila:
        pytest.skip("No hay tasaciones puntuadas")
    return fila[0]


def test_lista_y_ficha():
    tid = _una_tasacion()
    assert cliente.get("/").status_code == 200
    r = cliente.get(f"/tasacion/{tid}")
    assert r.status_code == 200 and 'id="datos-mapa"' in r.text
    assert cliente.get("/tasacion/999999").status_code == 404


def test_revision():
    tid = _una_tasacion()
    try:
        r = cliente.post(f"/tasacion/{tid}/revision", follow_redirects=False, data={
            "revisor": "test-web", "veredicto": "dudas", "valor_estimado": "250.000",
            "motivos": ["VALOR_AVM"], "comentario": "prueba"})
        assert r.status_code == 303
        with psycopg.connect(DATABASE_URL) as conn:
            fila = conn.execute("SELECT veredicto, valor_estimado, motivos FROM scoring.revision "
                                "WHERE revisor = 'test-web' AND tasacion_id = %s", (tid,)).fetchone()
        assert fila == ("dudas", 250000, ["VALOR_AVM"])
        assert cliente.post(f"/tasacion/{tid}/revision", data={"revisor": "x", "veredicto": "otro"}).status_code == 400
    finally:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("DELETE FROM scoring.revision WHERE revisor = 'test-web'")
