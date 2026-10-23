# Instalación

El sistema necesita tres piezas:

1. **PostgreSQL 17 + PostGIS 3.5**: la base de datos (esquema en `db/migrations/`).
2. **Python ≥ 3.13** con las dependencias del proyecto (descargadores, extracción, scoring).
3. **GDAL/OGR** (`ogr2ogr`): para cargar en PostGIS los GML de Catastro y los shapefiles de zonas inundables.

Cada pieza se puede instalar de varias formas. La combinación recomendada para desarrollo es la **A + uv + GDAL del sistema**.

---

## 1. Base de datos

### A. Docker Compose (recomendada)

```bash
cp .env.example .env            # opcional: cambia POSTGRES_PASSWORD
docker compose up -d
docker compose exec db psql -U tasacion -d tasacion -c '\dn'
```

- Expone Postgres en `localhost:5433`, para no chocar con un Postgres local en el 5432.
- Las migraciones de `db/migrations/*.sql` se aplican **solo la primera vez** que se crea el volumen. Para empezar de cero: `docker compose down -v && docker compose up -d`.
- Los datos viven en el volumen `pgdata`. Para guardarlos en otro disco, cambia el volumen por un *bind mount* (`- /ruta/grande/pgdata:/var/lib/postgresql/data`).

### B. PostgreSQL nativo

**Arch Linux**
```bash
sudo pacman -S postgresql postgis
sudo -iu postgres initdb -D /var/lib/postgres/data
sudo systemctl enable --now postgresql
```

**Debian / Ubuntu** (repositorio oficial PGDG)
```bash
sudo apt install -y postgresql-common
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt install -y postgresql-17 postgresql-17-postgis-3
```

**macOS**
```bash
brew install postgresql@17 postgis
brew services start postgresql@17
```

Después, en cualquiera de los tres:
```bash
sudo -iu postgres createuser -P tasacion
sudo -iu postgres createdb -O tasacion tasacion
sudo -iu postgres psql -d tasacion -c 'CREATE EXTENSION postgis; CREATE EXTENSION pg_trgm;'
for f in db/migrations/*.sql; do psql "postgresql://tasacion@localhost:5432/tasacion" -f "$f"; done
export DATABASE_URL=postgresql://tasacion:<password>@localhost:5432/tasacion
```

### C. Postgres gestionado (entornos compartidos o de producción)

Cualquier servicio que soporte PostGIS y `pg_trgm`, por ejemplo AWS RDS / Aurora PostgreSQL, Google Cloud SQL, Azure Database for PostgreSQL, Supabase o Neon.

- Activa las extensiones `postgis` y `pg_trgm` (según el proveedor, desde la consola o con `CREATE EXTENSION`).
- Aplica `db/migrations/*.sql` con `psql "$DATABASE_URL" -f ...`.
- Para clientes bancarios, elige una **región UE** y cifrado en reposo. Los datos del esquema `pii` deben quedar con permisos restringidos.

---

## 2. Python

### uv (recomendada)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # o: pacman -S uv / brew install uv
uv sync
uv run tasacion --help
```

### pip + venv
```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
tasacion --help
```

### Docker
Todavía no hay imagen de la aplicación; se añadirá cuando exista el servicio web.

---

## 3. GDAL / ogr2ogr

| Sistema | Comando |
|---|---|
| Arch | `sudo pacman -S gdal` |
| Debian/Ubuntu | `sudo apt install gdal-bin` |
| macOS | `brew install gdal` |
| Sin instalar nada (Docker) | `docker run --rm --network host -v "$PWD/data:/data" ghcr.io/osgeo/gdal:ubuntu-small-latest ogr2ogr ...` |

Comprueba que tiene los drivers que necesitamos:
```bash
ogr2ogr --formats | grep -E 'GML|ESRI Shapefile|PostgreSQL'
```

---

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | `postgresql://tasacion:tasacion@localhost:5433/tasacion` | Conexión a Postgres |
| `TASACION_DATA_DIR` | `./data` | Dónde se guardan los ficheros descargados (`<dir>/raw/<fuente>/<fecha>/`) |
| `POSTGRES_PASSWORD` | `tasacion` | Contraseña del contenedor Docker |

---

## Espacio en disco

> Catastro está **medido** sobre los feeds INSPIRE (agosto de 2026). El resto son estimaciones que se actualizarán tras la primera descarga completa.

| Componente | Ficheros crudos | Cargado en PostGIS (con índices) | Notas |
|---|---|---|---|
| Catastro INSPIRE, España de régimen común | **21,5 GB comprimido** (CP 14,3 + BU 6,5 + AD 0,7) | ~50–100 GB | El GML ocupa ~25× al descomprimirlo (~500 GB): **no se descomprime en disco**, se carga municipio a municipio en streaming. País Vasco y Navarra no están incluidos (catastros forales). |
| Certificados energéticos (Madrid, C. Valenciana, Aragón, Canarias, Cataluña) | ~1 GB | ~2–4 GB | |
| Estadísticas (MIVAU, INE, Registradores) | ~22 MB | < 1 GB | Medido. |
| Zonas inundables (SNCZI), si se cargan los shapefiles | ~2,3 GB | ~5–10 GB | Opcional: en el MVP se consulta por punto vía WMS. |
| Sumarios BOE desde 2015 (subastas en la sección V-B) | ~1,5 GB JSON | < 2 GB | |
| Anuncios (scraping) | ~1–3 GB al mes | ~5–15 GB al año | Solo se guarda una nueva observación cuando cambia el precio o el anuncio. |
| Fotos de anuncios | **cientos de GB a TB** si se guardan las imágenes | — | **No se guardan**: solo el hash perceptual (8 bytes) y la URL. |
| PDFs de tasaciones (histórico piloto de 2–5 k) | ~25–75 GB | ~1 GB extraído | De 5 a 15 MB por PDF, con fotos. |

**Orden de magnitud total para el MVP: 100–250 GB.** Recomendación: un disco o volumen dedicado de **500 GB** para `TASACION_DATA_DIR` y los datos de Postgres.

---

## Descarga de fuentes

```bash
uv run tasacion descargar estadisticas          # MIVAU, INE, Registradores (~1 min)
uv run tasacion descargar certificados          # registros autonómicos de certificados energéticos
uv run tasacion descargar boe                   # sumarios diarios desde 2015-10-15 (~1-2 h)
uv run tasacion descargar catastro              # toda España, ~21,5 GB (horas)
uv run tasacion descargar catastro --provincia 28 --capa BU   # sólo una provincia o capa
```

- Los ficheros se guardan en `data/raw/<fuente>/<fecha>/` y se registran en `ingest.raw_file` con su sha256.
- Todos los descargadores son **reanudables**: si se cortan, al relanzarlos se salta lo que ya estaba descargado.

Las siguientes fuentes se descargan **a mano** porque exigen identificación o un formulario:

| Fuente | Dónde | Guardar en |
|---|---|---|
| Catastro alfanumérico (formato CAT) | Sede Electrónica del Catastro → Descarga de datos (certificado o Cl@ve) | `data/raw/catastro_cat/` |
| Zonas inundables (shapefiles) | `https://www.miteco.gob.es/es/cartografia-y-sig/ide/descargas/agua/zi-lamina.html` | `data/raw/snczi/` |
| Sociedades de tasación homologadas | Registro de entidades del BdE: `https://app.bde.es/rbe_spa/home#/buscador` | tabla `tasacion.sociedad` |
| Nota simple | `https://sede.registradores.org` (de pago, por finca) | `data/raw/nota_simple/` |
