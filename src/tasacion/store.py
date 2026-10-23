"""Almacén de ficheros crudos: guarda en disco y registra procedencia en ingest.raw_file."""

import gzip
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx
import psycopg

DATA_DIR = Path(os.environ.get("TASACION_DATA_DIR", "data")) / "raw"
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://tasacion:tasacion@localhost:5433/tasacion"
)
# Varios servidores públicos (MIVAU, Registradores, BdE, BOE) rechazan User-Agents no
# de navegador. Nos identificamos además con la cabecera From.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36 tasacion-ia/0.1"
)
CONTACT = os.environ.get("TASACION_CONTACT")


@dataclass
class StoredFile:
    raw_file_id: int
    path: Path
    sha256: str
    nuevo: bool


def http_client(headers: dict | None = None, **kwargs) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT}
        | ({"From": CONTACT} if CONTACT else {})
        | (headers or {}),
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, read=300.0),
        **kwargs,
    )


def ya_descargado(source: str, url: str) -> bool:
    """True si ya tenemos un fichero de `source` descargado desde `url` (para reanudar)."""
    with psycopg.connect(DATABASE_URL) as conn:
        return (
            conn.execute(
                "SELECT 1 FROM ingest.raw_file WHERE source = %s AND origin_url = %s LIMIT 1",
                (source, url),
            ).fetchone()
            is not None
        )


def download(
    client: httpx.Client,
    source: str,
    url: str,
    filename: str,
    metadata: dict | None = None,
    **request_kwargs,
) -> StoredFile:
    """Descarga `url` en streaming a data/raw/<source>/<fecha>/<filename> y la registra.

    Si el mismo contenido (sha256) ya estaba registrado para esa fuente, se reutiliza.
    """
    target_dir = DATA_DIR / source / date.today().isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp = target_dir / f".{filename}.part"
    digest = hashlib.sha256()
    with client.stream("GET", url, **request_kwargs) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "").split(";")[0] or None
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(1 << 20):
                fh.write(chunk)
                digest.update(chunk)
    path = target_dir / filename
    tmp.replace(path)
    return register(source, path, digest.hexdigest(), url, content_type, metadata)


def register(
    source: str,
    path: Path,
    sha256: str,
    origin_url: str | None,
    content_type: str | None,
    metadata: dict | None = None,
) -> StoredFile:
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute(
            """
            INSERT INTO ingest.raw_file
                (source, origin_url, storage_uri, sha256, content_type, size_bytes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source, sha256) DO NOTHING
            RETURNING id
            """,
            (
                source,
                origin_url,
                str(path.resolve()),
                sha256,
                content_type,
                path.stat().st_size,
                json.dumps(metadata or {}),
            ),
        ).fetchone()
        if row:
            return StoredFile(row[0], path, sha256, nuevo=True)
        existing = conn.execute(
            "SELECT id, storage_uri FROM ingest.raw_file WHERE source = %s AND sha256 = %s",
            (source, sha256),
        ).fetchone()
    # Contenido repetido: borramos la copia nueva y apuntamos a la ya registrada.
    if Path(existing[1]).resolve() != path.resolve():
        path.unlink()
    return StoredFile(existing[0], Path(existing[1]), sha256, nuevo=False)


def save_bytes(
    source: str,
    filename: str,
    content: bytes,
    origin_url: str | None = None,
    content_type: str | None = None,
    metadata: dict | None = None,
    compress: bool = False,
) -> StoredFile:
    """Guarda contenido ya obtenido (p.ej. una página scrapeada), opcionalmente en gzip."""
    target_dir = DATA_DIR / source / date.today().isoformat()
    target_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(content).hexdigest()
    if compress:
        content = gzip.compress(content)
        filename += ".gz"
    path = target_dir / filename
    path.write_bytes(content)
    return register(source, path, sha, origin_url, content_type, metadata)
