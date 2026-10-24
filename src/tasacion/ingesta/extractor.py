"""Extracción de un PDF de tasación al esquema TasacionExtraida con Claude.

El PDF se envía entero como bloque `document` (PDFs nativos y escaneados: Claude lee el texto
y las imágenes de cada página). La salida va restringida al esquema con structured outputs.
"""

import base64
import logging
from pathlib import Path

import anthropic

from tasacion.ingesta.esquema import TasacionExtraida

log = logging.getLogger(__name__)

MODELO = "claude-opus-5-5"
VERSION = "extractor-v1"

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
- En `avisos_extraccion`, anota contradicciones internas del propio informe (p.ej. dos \
superficies distintas para la misma finca) y cualquier parte que no hayas podido leer.
- No extraigas datos personales del solicitante ni de los titulares (nombres, NIF, contacto).
"""


def extraer(pdf: Path, client: anthropic.Anthropic | None = None) -> tuple[TasacionExtraida, dict]:
    """Devuelve la extracción validada y metadatos de la llamada (modelo, uso, request id)."""
    client = client or anthropic.Anthropic()
    datos = base64.standard_b64encode(pdf.read_bytes()).decode()
    response = client.beta.messages.parse(
        model=MODELO,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=SISTEMA,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": datos},
                },
                {"type": "text", "text": "Extrae este informe de tasación."},
            ],
        }],
        output_format=TasacionExtraida,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"El modelo rechazó la extracción: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Extracción truncada por max_tokens")
    meta = {
        "modelo": response.model,
        "version": VERSION,
        "request_id": response._request_id,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return response.parsed_output, meta
