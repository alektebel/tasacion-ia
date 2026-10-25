"""Modelo ligero para tareas pequeñas (normalizar direcciones...) vía la API compatible OpenAI de NAN.

La extracción de informes sigue con Claude (ingesta/extractor.py); esto es para llamadas cortas
y numerosas donde basta un modelo pequeño. NAN_API_KEY debe estar en el entorno.
"""

import json
import os

from tasacion.store import http_client

NAN_URL = os.environ.get("NAN_BASE_URL", "https://api.nan.builders/v1").rstrip("/")
MODELO = os.environ.get("TASACION_MODELO_LIGERO", "qwen3.6")


def json_chat(sistema: str, usuario: str, max_tokens: int = 400) -> dict:
    """Una pregunta y una respuesta JSON (objeto), sin razonamiento y a temperatura 0."""
    clave = os.environ.get("NAN_API_KEY")
    if not clave:
        raise RuntimeError("Falta NAN_API_KEY en el entorno")
    payload = {
        "model": MODELO,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        # qwen3.x piensa por defecto: para extraer campos sólo añade latencia.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    # El CDN de NAN rechaza User-Agents que no son de navegador: http_client ya lo pone.
    with http_client({"Authorization": f"Bearer {clave}"}) as client:
        resp = client.post(f"{NAN_URL}/chat/completions", json=payload, timeout=60)
    resp.raise_for_status()
    eleccion = resp.json()["choices"][0]
    if eleccion.get("finish_reason") == "length":
        raise RuntimeError("Respuesta truncada por max_tokens")
    return json.loads(eleccion["message"]["content"])
