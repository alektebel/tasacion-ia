import json
import logging
from datetime import date

import typer

app = typer.Typer(help="Validación de tasaciones inmobiliarias ECO/805.")
descargar = typer.Typer(help="Descarga de fuentes externas a data/raw/ y registro en ingest.raw_file.")
app.add_typer(descargar, name="descargar")


@app.callback()
def _setup(verbose: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _print(stats: dict):
    typer.echo(json.dumps(stats, indent=2, ensure_ascii=False))


@descargar.command("catastro")
def descargar_catastro(
    capa: list[str] = typer.Option(["CP", "BU", "AD"], help="CP, BU y/o AD"),
    provincia: list[str] = typer.Option(None, help="Código de gerencia (p.ej. 28). Por defecto, todas."),
    workers: int = 4,
):
    """Catastro INSPIRE: un ZIP GML por municipio y capa. Reanudable."""
    from tasacion.fuentes import catastro

    _print(catastro.descargar([c.upper() for c in capa], provincia or None, workers))


@descargar.command("estadisticas")
def descargar_estadisticas():
    """MIVAU (valor tasado, transacciones), INE (IPV) y Registradores (€/m² por provincia)."""
    from tasacion.fuentes import estadisticas

    _print(estadisticas.descargar())


@descargar.command("certificados")
def descargar_certificados():
    """Registros de certificados energéticos: Madrid, C. Valenciana, Aragón, Canarias, Cataluña."""
    from tasacion.fuentes import certificados

    _print(certificados.descargar())


@descargar.command("boe")
def descargar_boe(
    desde: str = typer.Option("2015-10-15", help="AAAA-MM-DD"),
    hasta: str = typer.Option(None, help="AAAA-MM-DD; por defecto hoy"),
):
    """Sumarios diarios del BOE (subastas en la sección V-B). Reanudable."""
    from tasacion.fuentes import boe

    _print(boe.descargar(date.fromisoformat(desde), date.fromisoformat(hasta) if hasta else None))
