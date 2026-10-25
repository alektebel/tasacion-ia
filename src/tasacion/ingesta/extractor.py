"""Extracción de un PDF de tasación al esquema TasacionExtraida con Claude.

El PDF se envía entero como bloque `document` (PDFs nativos y escaneados: Claude lee el texto
y las imágenes de cada página).

No se usa structured outputs estricto: la API limita a 16 los campos con unión (nullable) y el
esquema de una tasación tiene más de cien. El esquema JSON va en el prompt, la respuesta se
valida con Pydantic y, si no valida, se reintenta una vez devolviendo el error al modelo.
"""

import base64
import json
import logging
import re
from pathlib import Path

import anthropic
from pydantic import ValidationError

from tasacion.ingesta.esquema import TasacionExtraida

log = logging.getLogger(__name__)

MODELO = "claude-opus-5-5"
VERSION = "extractor-v3"
MAX_INTENTOS = 2

SISTEMA = """\
Extraes datos de informes de tasación inmobiliaria españoles (Orden ECO/805/2003, reformada \
por la ECM/599/2025) para un sistema que valida esas tasaciones contra fuentes externas.

- Copia los valores tal como aparecen en el informe; no corrijas ni completes con conocimiento \
externo. Si un dato no está, devuelve null. Un null es mucho mejor que un valor supuesto.
- Importes en euros y superficies en m², como números (1.234,56 -> 1234.56).
- Fechas en formato AAAA-MM-DD.
- Una finca por cada elemento valorado (vivienda, garaje, trastero...). Los testigos van \
dentro de la finca a la que se refieren, en el orden del informe, con su desglose de \
coeficientes de homogeneización si existe.
- En `evidencias`, cita el fragmento literal y la página de cada valor, superficie, \
referencia catastral, fecha y testigo. Marca la confianza como baja si el texto es dudoso \
o la página es difícil de leer.
- En `avisos_extraccion`, anota cada problema clasificado: contradicciones del informe consigo \
mismo o con sus anexos (nota simple, ficha catastral), lagunas frente a lo que exige la ECO/805 \
y, aparte, tus propias notas de lectura. Sé concreto: cifras, páginas, qué dice cada parte.
- No extraigas datos personales del solicitante ni de los titulares (nombres, NIF, contacto).

Responde sólo con un objeto JSON que valide contra este esquema (todas las claves presentes, \
null cuando no haya dato), sin texto adicional:

""" + json.dumps(TasacionExtraida.model_json_schema(), ensure_ascii=False)


def _json(texto: str) -> str:
    """Quita un posible bloque ```json ... ``` alrededor de la respuesta."""
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    return m.group(1) if m else texto


def extraer(pdf: Path, client: anthropic.Anthropic | None = None) -> tuple[TasacionExtraida, dict]:
    """Devuelve la extracción validada y metadatos de la llamada (modelo, uso, request id)."""
    client = client or anthropic.Anthropic()
    datos = base64.standard_b64encode(pdf.read_bytes()).decode()
    mensajes = [{
        "role": "user",
        "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": datos}},
            {"type": "text", "text": "Extrae este informe de tasación."},
        ],
    }]
    uso = {"input_tokens": 0, "output_tokens": 0}
    for intento in range(1, MAX_INTENTOS + 1):
        # Streaming: con max_tokens alto el SDK lo exige para evitar timeouts HTTP.
        with client.beta.messages.stream(
            model=MODELO,
            max_tokens=64000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            system=SISTEMA,
            messages=mensajes,
        ) as stream:
            response = stream.get_final_message()
        uso["input_tokens"] += response.usage.input_tokens
        uso["output_tokens"] += response.usage.output_tokens
        if response.stop_reason == "refusal":
            raise RuntimeError(f"El modelo rechazó la extracción: {response.stop_details}")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Extracción truncada por max_tokens")
        texto = "".join(b.text for b in response.content if b.type == "text")
        try:
            extraida = TasacionExtraida.model_validate_json(_json(texto))
            break
        except ValidationError as exc:
            log.warning("intento %d: la respuesta no valida (%d errores)", intento, exc.error_count())
            if intento == MAX_INTENTOS:
                raise
            mensajes += [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": f"El JSON no valida contra el esquema. Corrígelo y devuelve el objeto completo:\n{exc}"},
            ]
    meta = {
        "modelo": response.model,
        "version": VERSION,
        "message_id": response.id,
        "intentos": intento,
        **uso,
    }
    return extraida, meta
