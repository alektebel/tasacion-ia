"""Un documento público o sin contraste no debe obtener validación hipotecaria."""

import pytest

from tasacion.scoring import reglas


@pytest.mark.parametrize("finalidad,metodo,tipo", [
    ("determinar_valor_mercado (no válida a efectos ECO/805)", "comparacion", "vivienda"),
    ("asesoramiento", "residual_estatico", "otro"),
    (None, "comparacion", "vivienda"),
    ("garantia_hipotecaria", None, "vivienda"),
    ("garantia_hipotecaria", "comparacion", "local"),
])
def test_fuera_de_alcance(finalidad, metodo, tipo):
    checks = reglas.r_alcance({"finalidad": finalidad, "metodo_principal": metodo}, {"tipo": tipo})
    assert checks and checks[0].bloqueante and checks[0].resultado == "fallo"


def test_alcance_hipotecario_residencial():
    assert reglas.r_alcance({"finalidad": "garantia_hipotecaria", "metodo_principal": "comparacion"},
                            {"tipo": "vivienda"}) == []


def test_sin_finca():
    assert reglas.r_alcance({"finalidad": "garantia_hipotecaria", "metodo_principal": "comparacion"},
                            None)[0].bloqueante


@pytest.mark.parametrize("chequeos,sub,esperado", [
    ([reglas.Chequeo("AVM", "valor", "no_evaluable", "Sin comparables")],
     {"valor": 1, "calidad": 1, "fraude": 1}, "dudas"),
    ([], {"valor": 1, "calidad": 1, "fraude": 1}, "dudas"),
    ([reglas.Chequeo("RC", "calidad", "ok", "Coincide")],
     {"valor": 1, "calidad": 1, "fraude": 1}, "validada"),
    ([reglas.Chequeo("ALCANCE", "calidad", "fallo", "Fuera", bloqueante=True)],
     {"valor": 1, "calidad": 1, "fraude": 1}, "revision_obligatoria"),
    ([reglas.Chequeo("RC", "calidad", "fallo", "No coincide")],
     {"valor": 1, "calidad": 1, "fraude": 1}, "dudas"),
    ([reglas.Chequeo("RC", "calidad", "aviso", "Diferencia")],
     {"valor": 1, "calidad": 0.4, "fraude": 1}, "revision_obligatoria"),
    ([reglas.Chequeo("RC", "calidad", "aviso", "Diferencia")],
     {"valor": 1, "calidad": 0.7, "fraude": 1}, "dudas"),
])
def test_veredicto(chequeos, sub, esperado):
    assert reglas.veredicto(chequeos, sub) == esperado
