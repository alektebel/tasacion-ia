"""Muestras oficiales: integridad del PDF y regresión sobre campos leídos a mano."""

import hashlib
import json

import httpx
import pytest

from tasacion.ingesta import muestras
from tasacion.ingesta.esquema import TasacionExtraida


def extraccion():
    datos = dict.fromkeys(TasacionExtraida.model_fields)
    datos.update(valor_tasacion=180025.46, fecha_emision="2021-09-10", fincas=[],
                 condicionantes=[], advertencias=[], avisos_extraccion=[], evidencias=[])
    return datos


def muestra():
    pdf = b"%PDF-1.4\nprueba"
    return {"archivo": "prueba.pdf", "url": "https://example.org/prueba.pdf",
            "sha256": hashlib.sha256(pdf).hexdigest(), "paginas_pdf": 37,
            "campos": {"/valor_tasacion": 180025.46, "/fecha_emision": "2021-09-10"},
            "recuentos": {"/fincas": 0}}


def test_descarga_y_cache(tmp_path, monkeypatch):
    solicitudes = []

    def responder(request):
        solicitudes.append(request)
        return httpx.Response(200, content=b"%PDF-1.4\nprueba")

    monkeypatch.setattr(muestras, "http_client", lambda: httpx.Client(
        transport=httpx.MockTransport(responder)))
    path = muestras.preparar_pdf(muestra(), tmp_path)
    assert path.read_bytes().startswith(b"%PDF-")
    assert muestras.preparar_pdf(muestra(), tmp_path) == path
    assert len(solicitudes) == 1


@pytest.mark.parametrize("contenido", [b"<html>Request Rejected</html>", b"%PDF-1.4\ncambiado"])
def test_rechaza_descarga_invalida(tmp_path, monkeypatch, contenido):
    monkeypatch.setattr(muestras, "http_client", lambda: httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=contenido))))
    with pytest.raises(ValueError):
        muestras.preparar_pdf(muestra(), tmp_path)
    assert not (tmp_path / "prueba.pdf").exists()


def test_no_sobrescribe_pdf_local_distinto(tmp_path):
    path = tmp_path / "prueba.pdf"
    path.write_bytes(b"%PDF-1.4\notro")
    with pytest.raises(ValueError, match="SHA-256"):
        muestras.preparar_pdf(muestra(), tmp_path)
    assert path.read_bytes() == b"%PDF-1.4\notro"


def test_regresion_campos_y_metadatos():
    datos = extraccion()
    datos["_meta"] = {"sha256": muestra()["sha256"]}
    assert muestras.comprobar(datos, muestra()) == []
    datos["valor_tasacion"] = 18002546  # error de separador decimal
    datos["fecha_emision"] = None
    datos["_meta"]["sha256"] = "otro"
    fallos = muestras.comprobar(datos, muestra())
    assert len(fallos) == 3
    assert any("/valor_tasacion" in f for f in fallos)


def test_recuentos_rutas_ausentes_y_paginas():
    datos = extraccion()
    datos["evidencias"] = [{"ruta": "valor_tasacion", "pagina": 38,
                           "texto": "valor", "confianza": "alta"}]
    caso = muestra()
    caso["campos"]["/fincas/0/sup_adoptada"] = 103
    caso["recuentos"]["/fincas"] = 1
    fallos = muestras.comprobar(datos, caso)
    assert len(fallos) == 3


def test_esquema_invalido():
    with pytest.raises(ValueError):
        muestras.comprobar({"valor_tasacion": "no es un importe"}, muestra())


def test_cli_json_sin_llm(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "muestras.json"
    manifest.write_text(json.dumps({"prueba": muestra()}))
    archivo = tmp_path / "salida.json"
    archivo.write_text(json.dumps(extraccion()))
    (tmp_path / "prueba.pdf").write_bytes(b"%PDF-1.4\nprueba")
    args = ["prueba", "--manifest", str(manifest), "--directorio", str(tmp_path),
            "--json", str(archivo)]
    assert muestras.main(args) == 0
    assert "OK" in capsys.readouterr().out
    datos = extraccion()
    datos["valor_tasacion"] = 1
    archivo.write_text(json.dumps(datos))
    assert muestras.main(args) == 1


def test_cli_extraer_y_guardar(tmp_path, monkeypatch):
    from tasacion.ingesta import extractor

    manifest = tmp_path / "muestras.json"
    manifest.write_text(json.dumps({"prueba": muestra()}))
    (tmp_path / "prueba.pdf").write_bytes(b"%PDF-1.4\nprueba")
    monkeypatch.setattr(extractor, "extraer", lambda p: (
        TasacionExtraida.model_validate(extraccion()), {"modelo": "prueba"}))
    assert muestras.main(["prueba", "--manifest", str(manifest),
                          "--directorio", str(tmp_path), "--extraer"]) == 0
    guardado = json.loads((tmp_path / "prueba.extraida.json").read_text())
    assert guardado["_meta"]["sha256"] == muestra()["sha256"]


def test_cli_solo_preparar(tmp_path, capsys):
    manifest = tmp_path / "muestras.json"
    manifest.write_text(json.dumps({"prueba": muestra()}))
    (tmp_path / "prueba.pdf").write_bytes(b"%PDF-1.4\nprueba")
    assert muestras.main(["prueba", "--manifest", str(manifest),
                          "--directorio", str(tmp_path)]) == 0
    assert "--extraer" in capsys.readouterr().out
