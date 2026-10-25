"""Partes puras de la geolocalización de testigos y de la regla de distancia (sin red ni base de datos)."""

from tasacion.ingesta.geocodificar import _numero, _plano
from tasacion.scoring.reglas import r_distancia_testigos


def test_numero_y_nombre():
    assert _numero("Nº 0023") == "23"
    assert _numero("29-31") == "29"
    assert _numero("s/n") is None
    assert _plano("  Dulce  Chacón ") == "DULCE CHACON"


def _t(orden, distancia, precision="portal"):
    return {"orden": orden, "distancia_m": distancia, "geocodificacion_precision": precision}


def test_distancia_testigos():
    cerca = [_t(i, 300) for i in range(1, 6)]
    assert r_distancia_testigos(cerca)[0].resultado == "ok"
    # Sin portal se da holgura: 2,3 km al centro de la vía no cuenta como lejos.
    assert r_distancia_testigos(cerca + [_t(6, 2300, "calle")])[0].resultado == "ok"
    c = r_distancia_testigos(cerca + [_t(6, 2300)])[0]
    assert (c.resultado, c.observado) == ("aviso", [6])
    assert r_distancia_testigos(cerca + [_t(6, 6000)])[0].resultado == "fallo"
    assert r_distancia_testigos([_t(1, 3000), _t(2, 3000), _t(3, 100)])[0].resultado == "fallo"
    assert r_distancia_testigos([_t(1, None)])[0].resultado == "no_evaluable"


def test_planta():
    from tasacion.scoring.testigos_catastro import planta
    assert [planta(x) for x in ("9", "sótano -1", "sótano 2", "Bajo", "00", "BJ", "OD", "ático", None)] == \
        [9, -1, -2, 0, 0, 0, None, None, None]


def test_contrastar_testigo():
    from tasacion.scoring.testigos_catastro import contrastar
    edificio = [{"uso": "Residencial", "sup": 95.0, "anio": 2006, "planta": f"{p:02d}"} for p in range(0, 9)] + \
               [{"uso": "Almacen-Estacionamiento", "sup": 25.0, "anio": 2006, "planta": "-1"}]
    assert contrastar({"planta": "5", "sup_construida": 90, "anio_construccion": 2006}, "vivienda", edificio)[0] == "coherente"
    res, dif = contrastar({"planta": "12", "sup_construida": 150, "anio_construccion": 1990}, "vivienda", edificio)
    assert res == "discrepante" and [d["campo"] for d in dif] == ["planta", "superficie", "anio"]
    assert contrastar({"planta": "sótano -1"}, "garaje", edificio)[0] == "coherente"
    assert contrastar({}, "local", edificio)[1][0]["campo"] == "uso"
    assert contrastar({}, "vivienda", [])[0] == "no_encontrado"
