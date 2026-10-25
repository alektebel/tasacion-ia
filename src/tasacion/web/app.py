"""Vista web mínima para revisar tasaciones: listado, ficha con semáforo, motivos, evidencia y mapa.

Pensada para uso interno en local (`tasacion web`): lee directamente de la base de datos y no
tiene autenticación. La revisión del tasador senior se guarda en scoring.revision y es lo que
servirá para calibrar los umbrales de las reglas.
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import psycopg
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from psycopg.rows import dict_row
from starlette.requests import Request

from tasacion.scoring import testigos_catastro
from tasacion.store import DATABASE_URL

AQUI = Path(__file__).parent
app = FastAPI(title="Validación de tasaciones")
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
plantillas = Jinja2Templates(directory=AQUI / "templates")

VEREDICTOS = {
    "validada": ("Validada", "verde"),
    "dudas": ("Dudas", "ambar"),
    "revision_obligatoria": ("Revisión obligatoria", "rojo"),
}
CATEGORIAS = {"valor": "Valor", "calidad": "Calidad y cumplimiento", "fraude": "Fraude"}


def _euros(v) -> str:
    if v is None:
        return "—"
    return f"{float(v):,.0f} €".replace(",", ".")


def _num(v, dec: int = 0) -> str:
    if v is None:
        return "—"
    return f"{float(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


plantillas.env.filters["euros"] = _euros
plantillas.env.filters["num"] = _num
plantillas.env.globals["VEREDICTOS"] = VEREDICTOS
plantillas.env.globals["CATEGORIAS"] = CATEGORIAS


def _json_default(o):
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def _conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@app.get("/", response_class=HTMLResponse)
def lista(request: Request):
    with _conn() as conn:
        filas = conn.execute(
            """
            SELECT t.id, t.num_informe, t.fecha_emision, t.valor_tasacion, t.metodo_principal,
                   so.nombre AS sociedad, f.direccion, f.municipio,
                   s.veredicto, s.compuesto, s.motivos, s.version,
                   (SELECT count(*) FROM scoring.revision r WHERE r.tasacion_id = t.id) AS revisiones
            FROM tasacion.tasacion t
            LEFT JOIN tasacion.sociedad so ON so.id = t.sociedad_id
            LEFT JOIN LATERAL (
                SELECT direccion, municipio FROM tasacion.finca WHERE tasacion_id = t.id
                ORDER BY es_principal DESC, orden LIMIT 1) f ON true
            LEFT JOIN LATERAL (
                SELECT * FROM scoring.score WHERE tasacion_id = t.id ORDER BY created_at DESC LIMIT 1) s ON true
            ORDER BY t.id DESC
            """
        ).fetchall()
    return plantillas.TemplateResponse(request, "lista.html", {"tasaciones": filas})


def _ficha(conn: psycopg.Connection, tasacion_id: int) -> dict:
    t = conn.execute(
        """
        SELECT t.*, so.nombre AS sociedad, so.codigo_bde, te.nombre_normalizado AS tecnico,
               te.num_colegiado, r.storage_uri
        FROM tasacion.tasacion t
        LEFT JOIN tasacion.sociedad so ON so.id = t.sociedad_id
        LEFT JOIN tasacion.tecnico te ON te.id = t.tecnico_id
        LEFT JOIN ingest.raw_file r ON r.id = t.raw_file_id
        WHERE t.id = %s
        """, (tasacion_id,),
    ).fetchone()
    if not t:
        raise HTTPException(404, "Tasación no encontrada")
    fincas = conn.execute(
        "SELECT *, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM tasacion.finca WHERE tasacion_id = %s "
        "ORDER BY es_principal DESC, orden", (tasacion_id,),
    ).fetchall()
    principal = fincas[0] if fincas else None
    score = conn.execute(
        "SELECT * FROM scoring.score WHERE tasacion_id = %s ORDER BY created_at DESC LIMIT 1", (tasacion_id,),
    ).fetchone()
    # Chequeos y score se insertan en la misma transacción: comparten created_at.
    chequeos = conn.execute(
        """
        SELECT * FROM scoring.chequeo WHERE tasacion_id = %s AND created_at = %s
        ORDER BY CASE resultado WHEN 'fallo' THEN 0 WHEN 'aviso' THEN 1 WHEN 'ok' THEN 2 ELSE 3 END,
                 severidad DESC, id
        """, (tasacion_id, score["created_at"]),
    ).fetchall() if score else []
    testigos = conn.execute(
        """
        SELECT te.*, ST_Y(te.geom) AS lat, ST_X(te.geom) AS lon, f.tipo AS tipo_finca, f.orden AS orden_finca,
               ST_Distance(te.geom::geography, p.geom::geography) AS distancia_m,
               v.resultado AS catastro, v.diferencias AS catastro_detalle
        FROM tasacion.testigo te
        JOIN tasacion.finca f ON f.id = te.finca_id
        LEFT JOIN tasacion.finca p ON p.id = %s
        LEFT JOIN LATERAL (
            SELECT resultado, diferencias FROM scoring.verificacion_testigo
            WHERE testigo_id = te.id AND version = %s ORDER BY created_at DESC LIMIT 1) v ON true
        WHERE f.tasacion_id = %s ORDER BY f.orden, te.orden
        """, (principal["id"] if principal else None, testigos_catastro.VERSION, tasacion_id),
    ).fetchall()

    avm = next((c for c in chequeos if c["codigo"] == "VALOR_AVM"), None)
    ids = (avm["evidencia"] or {}).get("comparables", []) if avm else []
    comparables = conn.execute(
        """
        SELECT a.id, a.portal, a.url, a.sup_construida, ST_Y(a.geom) AS lat, ST_X(a.geom) AS lon, o.precio
        FROM fuente.anuncio a
        JOIN LATERAL (SELECT precio FROM fuente.anuncio_observacion
                      WHERE anuncio_id = a.id ORDER BY observado_en DESC LIMIT 1) o ON true
        WHERE a.id = ANY(%s)
        """, (ids,),
    ).fetchall() if ids else []
    revisiones = conn.execute(
        "SELECT * FROM scoring.revision WHERE tasacion_id = %s ORDER BY created_at DESC", (tasacion_id,),
    ).fetchall()

    # Citas literales del informe, por ruta del esquema (p.ej. «fincas/0/testigos/2»).
    evidencias = (t["extraccion_json"] or {}).get("evidencias") or []
    citas_testigo: dict[tuple[int, int], list[dict]] = {}
    for e in evidencias:
        if m := re.match(r"fincas/(\d+)/testigos/(\d+)", e.get("ruta") or ""):
            citas_testigo.setdefault((int(m[1]), int(m[2])), []).append(e)
    for te in testigos:
        te["citas"] = citas_testigo.get((te["orden_finca"] - 1, te["orden"] - 1), [])
    avisos = [a for a in (t["extraccion_json"] or {}).get("avisos_extraccion") or [] if isinstance(a, dict)]

    mapa = {
        "fincas": [{"lat": f["lat"], "lon": f["lon"], "tipo": f["tipo"], "direccion": f["direccion"],
                    "rc": f["ref_catastral"], "principal": f["es_principal"]} for f in fincas if f["lat"] is not None],
        "testigos": [{"orden": x["orden"], "lat": x["lat"], "lon": x["lon"], "direccion": x["direccion"],
                      "precio": x["precio"], "sup": x["sup_construida"] or x["sup_util"],
                      "eur_m2": x["precio_unitario"], "distancia": x["distancia_m"],
                      "precision": x["geocodificacion_precision"], "catastro": x["catastro"],
                      "tipo": x["tipo_finca"]} for x in testigos if x["lat"] is not None],
        "comparables": [{"lat": c["lat"], "lon": c["lon"], "precio": c["precio"], "sup": c["sup_construida"],
                         "portal": c["portal"], "url": c["url"]} for c in comparables],
    }
    return {"t": t, "fincas": fincas, "principal": principal, "score": score, "chequeos": chequeos,
            "testigos": testigos, "comparables": comparables, "revisiones": revisiones, "avisos": avisos,
            "evidencias": evidencias, "n_evidencias": len(evidencias),
            # Va dentro de un <script>: «</» cerraría la etiqueta si aparece en una dirección.
            "mapa_json": json.dumps(mapa, default=_json_default, ensure_ascii=False).replace("</", "<\\/")}


@app.get("/tasacion/{tasacion_id}", response_class=HTMLResponse)
def ficha(request: Request, tasacion_id: int):
    with _conn() as conn:
        ctx = _ficha(conn, tasacion_id)
    return plantillas.TemplateResponse(request, "ficha.html", ctx)


@app.get("/tasacion/{tasacion_id}/pdf")
def pdf(tasacion_id: int):
    with _conn() as conn:
        fila = conn.execute(
            "SELECT r.storage_uri FROM tasacion.tasacion t JOIN ingest.raw_file r ON r.id = t.raw_file_id "
            "WHERE t.id = %s", (tasacion_id,),
        ).fetchone()
    if not fila or not Path(fila["storage_uri"]).is_file():
        raise HTTPException(404, "PDF no disponible")
    return FileResponse(fila["storage_uri"], media_type="application/pdf",
                        headers={"Content-Disposition": "inline"})


@app.post("/tasacion/{tasacion_id}/revision")
def revisar(
    tasacion_id: int,
    revisor: str = Form(...),
    veredicto: str = Form(...),
    valor_estimado: str = Form(""),
    motivos: list[str] = Form([]),
    comentario: str = Form(""),
):
    if veredicto not in VEREDICTOS or not revisor.strip():
        raise HTTPException(400, "Revisor y veredicto son obligatorios")
    valor = float(valor_estimado.replace(".", "").replace(",", ".")) if valor_estimado.strip() else None
    with _conn() as conn:
        score = conn.execute(
            "SELECT id FROM scoring.score WHERE tasacion_id = %s ORDER BY created_at DESC LIMIT 1", (tasacion_id,),
        ).fetchone()
        conn.execute(
            "INSERT INTO scoring.revision (tasacion_id, score_id, revisor, veredicto, valor_estimado, motivos, comentario) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (tasacion_id, score["id"] if score else None, revisor.strip(), veredicto, valor,
             motivos or None, comentario.strip() or None),
        )
    return RedirectResponse(f"/tasacion/{tasacion_id}#revision", status_code=303)
