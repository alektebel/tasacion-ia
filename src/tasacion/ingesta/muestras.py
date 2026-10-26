"""Descarga y comprueba muestras públicas sin BD; la extracción LLM es optativa."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from tasacion.ingesta.esquema import TasacionExtraida
from tasacion.store import http_client


def preparar_pdf(muestra: dict, directorio: Path) -> Path:
    path = directorio / muestra["archivo"]
    if path.exists():
        contenido = path.read_bytes()
    else:
        with http_client() as client:
            resp = client.get(muestra["url"], timeout=60)
            resp.raise_for_status()
            contenido = resp.content
    if not contenido.startswith(b"%PDF-"):
        raise ValueError("La fuente no ha devuelto un PDF")
    if hashlib.sha256(contenido).hexdigest() != muestra["sha256"]:
        raise ValueError("SHA-256 distinto: revisar el documento antes de actualizar la referencia")
    if not path.exists():
        directorio.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contenido)
    return path


def _valor(datos: dict, ruta: str):
    valor = datos
    try:
        for parte in ruta.strip("/").split("/"):
            valor = valor[int(parte)] if isinstance(valor, list) else valor[parte]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return valor


def comprobar(datos: dict, muestra: dict) -> list[str]:
    """Comprueba el esquema y un subconjunto de campos revisados, no la validez legal."""
    extraida = TasacionExtraida.model_validate(datos)
    fallos = []
    sha = (datos.get("_meta") or {}).get("sha256")
    if sha is not None and sha != muestra["sha256"]:
        fallos.append("La extracción pertenece a otro SHA-256")
    for ruta, esperado in muestra["campos"].items():
        valor = _valor(datos, ruta)
        iguales = valor == esperado
        if isinstance(esperado, (int, float)) and not isinstance(esperado, bool):
            iguales = (isinstance(valor, (int, float)) and not isinstance(valor, bool)
                       and math.isclose(valor, esperado, rel_tol=0, abs_tol=0.01))
        if not iguales:
            fallos.append(f"{ruta}: esperado {esperado!r}, recibido {valor!r}")
    for ruta, esperado in muestra["recuentos"].items():
        valor = _valor(datos, ruta)
        if not isinstance(valor, list) or len(valor) != esperado:
            fallos.append(f"{ruta}: se esperaban {esperado} elementos")
    for evidencia in extraida.evidencias:
        if evidencia.pagina is not None and not 1 <= evidencia.pagina <= muestra["paginas_pdf"]:
            fallos.append(f"{evidencia.ruta}: página fuera del PDF ({evidencia.pagina})")
    return fallos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("muestra", help="Identificador del manifiesto, p.ej. coslada")
    parser.add_argument("--manifest", type=Path, default=Path("examples/tasaciones/muestras.json"))
    parser.add_argument("--directorio", type=Path, default=Path("data/raw/tasaciones_publicas"))
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--json", type=Path, help="Comprobar una extracción ya guardada, sin llamar al LLM")
    modo.add_argument("--extraer", action="store_true", help="Enviar el PDF a Anthropic y comprobar la salida")
    args = parser.parse_args(argv)
    catalogo = json.loads(args.manifest.read_text())
    if args.muestra not in catalogo:
        parser.error(f"Muestra desconocida; disponibles: {', '.join(catalogo)}")
    muestra = catalogo[args.muestra]
    pdf = preparar_pdf(muestra, args.directorio)
    print(f"PDF verificado: {pdf}")
    print(f"Uso de la muestra: {muestra.get('alcance', 'regresión de extracción')}")
    if args.extraer:
        from tasacion.ingesta.extractor import extraer

        extraida, meta = extraer(pdf)
        datos = extraida.model_dump(mode="json")
        datos["_meta"] = meta | {"sha256": muestra["sha256"]}
        salida = pdf.with_suffix(".extraida.json")
        salida.write_text(json.dumps(datos, ensure_ascii=False, indent=2))
        print(f"Extracción guardada: {salida}")
    elif args.json:
        datos = json.loads(args.json.read_text())
    else:
        print("Añade --extraer para ejecutar el parser (requiere Anthropic), o --json RUTA para comprobar una salida existente.")
        return 0
    fallos = comprobar(datos, muestra)
    for fallo in fallos:
        print(f"FALLO: {fallo}")
    if not fallos:
        print(f"OK: esquema, {len(muestra['campos'])} campos, {len(muestra['recuentos'])} recuentos y límites de páginas. No certifica cumplimiento ECO.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
