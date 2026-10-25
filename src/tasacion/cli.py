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


@descargar.command("abiertos")
def descargar_abiertos(
    fuente: list[str] = typer.Option(None, help="Sólo estas fuentes (p.ej. osm, ine_adrh, gtfs). Por defecto, todas."),
):
    """Contexto abierto: renta INE, censo, SERPAVI, OSM, GTFS, ITE/IEE, más CEE, open data municipal."""
    from tasacion.fuentes import abiertos

    _print(abiertos.descargar(fuente or None))


@descargar.command("boe-subastas")
def descargar_boe_subastas():
    """Anuncios XML de subasta (Seguridad Social, AEAT...) citados en los sumarios ya descargados."""
    from tasacion.fuentes import boe

    _print(boe.descargar_anuncios())


scrapear = typer.Typer(help="Scraping de portales (I+D). Una petición por segundo; se para ante 403/429.")
app.add_typer(scrapear, name="scrapear")


@scrapear.command("pisoscom")
def scrapear_pisoscom(
    fase: str = typer.Argument(..., help="listados | fichas"),
    provincia: list[str] = typer.Option(None, help="Slug de pisos.com, p.ej. madrid. Por defecto, todas."),
    limite: int = typer.Option(None, help="Máximo de fichas (fase fichas)"),
    pausa: float = 1.0,
):
    """pisos.com: fase 'listados' (precio, m², URL) y fase 'fichas' (coordenadas, características)."""
    from tasacion.fuentes import pisoscom

    if fase == "listados":
        _print(pisoscom.listados(provincia or None, pausa))
    elif fase == "fichas":
        _print(pisoscom.fichas(limite, pausa))
    else:
        raise typer.BadParameter("fase debe ser 'listados' o 'fichas'")


@scrapear.command("fotocasa")
def scrapear_fotocasa(max_paginas: int = typer.Option(None), pausa: float = 1.0):
    """fotocasa.es: listado nacional (incluye coordenadas). Repetir para completar huecos."""
    from tasacion.fuentes import fotocasa

    _print(fotocasa.listados(pausa, max_paginas))


@app.command("ingerir")
def ingerir(
    pdf: list[str] = typer.Argument(..., help="Uno o varios PDFs de tasación"),
    operacion: str = typer.Option(None, help="Referencia de la operación en el banco"),
    solo_json: bool = typer.Option(False, help="Extraer e imprimir el JSON sin cargar en la base de datos"),
):
    """Extrae cada PDF con Claude al esquema ECO y lo carga en tasacion.*."""
    import hashlib
    from pathlib import Path

    from tasacion.ingesta import carga, extractor

    for ruta in pdf:
        path = Path(ruta)
        extraida, meta = extractor.extraer(path)
        meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        if solo_json:
            typer.echo(extraida.model_dump_json(indent=2))
            continue
        tasacion_id = carga.cargar(path, extraida, meta, operacion)
        typer.echo(f"{path.name}: tasación {tasacion_id} ({len(extraida.fincas)} fincas, "
                   f"{sum(len(f.testigos) for f in extraida.fincas)} testigos, "
                   f"{len(extraida.avisos_extraccion)} avisos)")


@app.command("avm")
def avm(lat: float, lon: float, sup: float = typer.Argument(..., help="Superficie construida, m²")):
    """Valor estimado por comparables para un punto y una superficie (sin guardar)."""
    from dataclasses import asdict

    from tasacion.scoring import avm as m

    est = m.estimar(lat, lon, sup)
    if est is None:
        typer.echo("Sin comparables suficientes")
        raise typer.Exit(1)
    resumen = {k: v for k, v in asdict(est).items() if k != "comparables"}
    resumen["top_comparables"] = [
        {k: round(v, 1) if isinstance(v, float) else v for k, v in c.items()} for c in est.comparables[:5]
    ]
    _print(resumen)


@app.command("puntuar")
def puntuar(tasacion_id: list[int] = typer.Argument(None, help="Ids de tasación; por defecto, todas las no puntuadas")):
    """Aplica las reglas, calcula sub-scores y semáforo, y lo guarda en scoring.*."""
    import psycopg

    from tasacion.scoring import reglas
    from tasacion.store import DATABASE_URL

    if not tasacion_id:
        with psycopg.connect(DATABASE_URL) as conn:
            tasacion_id = [r[0] for r in conn.execute(
                "SELECT id FROM tasacion.tasacion WHERE estado <> 'puntuada' ORDER BY id")]
    for tid in tasacion_id:
        _print(reglas.puntuar(tid))
