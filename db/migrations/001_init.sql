-- Esquema inicial de tasacion-ia.
--
-- Namespaces:
--   ingest   ficheros crudos (PDFs de tasaciones, descargas de fuentes) y su procedencia
--   tasacion lo extraído de cada informe ECO/805 + datos de la operación del banco
--   fuente   datos de referencia externos (Catastro, estadísticas, anuncios, subastas...)
--   scoring  AVM, verificación de testigos, chequeos, scores, revisiones y sesgo por tasador
--   pii      datos personales, separados para poder restringir permisos
--
-- Geometrías en EPSG:4326; las distancias se calculan con cast a geography.
-- Los "enums" son text + CHECK para poder ampliarlos sin migraciones de tipo.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA ingest;
CREATE SCHEMA tasacion;
CREATE SCHEMA fuente;
CREATE SCHEMA scoring;
CREATE SCHEMA pii;

-- ---------------------------------------------------------------------------
-- ingest
-- ---------------------------------------------------------------------------

-- Cada fichero que entra en el sistema, venga de un cliente o de una descarga.
-- El contenido vive en disco/objeto (storage_uri); aquí sólo procedencia e integridad.
CREATE TABLE ingest.raw_file (
    id            bigserial PRIMARY KEY,
    source        text NOT NULL,          -- 'cliente', 'catastro_inspire', 'mivau', 'ine', 'idealista', ...
    origin_url    text,
    storage_uri   text NOT NULL,
    sha256        char(64) NOT NULL,
    content_type  text,                   -- application/pdf, application/zip, text/csv, ...
    size_bytes    bigint,
    fetched_at    timestamptz NOT NULL DEFAULT now(),
    metadata      jsonb NOT NULL DEFAULT '{}',
    UNIQUE (source, sha256)
);

-- Una ejecución de un downloader o de la extracción de un lote de PDFs.
CREATE TABLE ingest.run (
    id           bigserial PRIMARY KEY,
    kind         text NOT NULL CHECK (kind IN ('download', 'extraction', 'load', 'scoring')),
    source       text NOT NULL,
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    status       text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'ok', 'error')),
    params       jsonb NOT NULL DEFAULT '{}',
    stats        jsonb NOT NULL DEFAULT '{}',
    error        text
);

CREATE TABLE ingest.run_file (
    run_id       bigint NOT NULL REFERENCES ingest.run(id) ON DELETE CASCADE,
    raw_file_id  bigint NOT NULL REFERENCES ingest.raw_file(id),
    PRIMARY KEY (run_id, raw_file_id)
);

-- ---------------------------------------------------------------------------
-- tasacion: maestros
-- ---------------------------------------------------------------------------

-- Sociedades de tasación (maestro alimentado desde el registro del Banco de España).
CREATE TABLE tasacion.sociedad (
    id            bigserial PRIMARY KEY,
    codigo_bde    text UNIQUE,
    nombre        text NOT NULL,
    cif           text UNIQUE,
    homologada    boolean,
    fecha_alta    date,
    fecha_baja    date,
    raw_file_id   bigint REFERENCES ingest.raw_file(id)
);

-- Técnico tasador. Clave natural: colegio + nº de colegiado.
CREATE TABLE tasacion.tecnico (
    id                 bigserial PRIMARY KEY,
    nombre_normalizado text NOT NULL,
    num_colegiado      text,
    colegio            text,
    titulacion         text,               -- arquitecto, arquitecto técnico, ingeniero...
    UNIQUE (colegio, num_colegiado)
);

-- Grafías vistas en los informes, para resolver duplicados.
CREATE TABLE tasacion.tecnico_alias (
    tecnico_id  bigint NOT NULL REFERENCES tasacion.tecnico(id) ON DELETE CASCADE,
    alias       text NOT NULL,
    PRIMARY KEY (tecnico_id, alias)
);
CREATE INDEX ON tasacion.tecnico_alias USING gin (alias gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- tasacion: operación (datos que aporta el banco junto al PDF)
-- ---------------------------------------------------------------------------

CREATE TABLE tasacion.operacion (
    id                  bigserial PRIMARY KEY,
    ref_cliente         text NOT NULL UNIQUE,   -- id de la operación en el banco
    precio_compraventa  numeric(14, 2),
    importe_prestamo    numeric(14, 2),
    ltv                 numeric(6, 4),
    fecha_operacion     date,
    oficina             text,
    canal               text,                   -- oficina, API, broker...
    finalidad           text,                   -- compra vivienda habitual, refinanciación...
    metadata            jsonb NOT NULL DEFAULT '{}'
);

-- Resultados observados a posteriori (impago, re-tasación, venta...). Etiquetas para la v2.
CREATE TABLE tasacion.operacion_resultado (
    id            bigserial PRIMARY KEY,
    operacion_id  bigint NOT NULL REFERENCES tasacion.operacion(id) ON DELETE CASCADE,
    tipo          text NOT NULL CHECK (tipo IN ('impago', 'retasacion', 'venta', 'adjudicacion', 'subasta', 'otro')),
    fecha         date NOT NULL,
    valor         numeric(14, 2),
    detalle       jsonb NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- tasacion: el informe
-- ---------------------------------------------------------------------------

CREATE TABLE tasacion.tasacion (
    id                     bigserial PRIMARY KEY,
    raw_file_id            bigint NOT NULL REFERENCES ingest.raw_file(id),
    operacion_id           bigint REFERENCES tasacion.operacion(id),
    sociedad_id            bigint REFERENCES tasacion.sociedad(id),
    tecnico_id             bigint REFERENCES tasacion.tecnico(id),
    num_informe            text,
    finalidad              text,              -- 'garantia_hipotecaria' (ECO art. 2a), ...
    normativa              text DEFAULT 'ECO/805/2003',
    fecha_visita           date,
    fecha_emision          date,
    fecha_caducidad        date,
    metodo_principal       text CHECK (metodo_principal IN ('comparacion', 'coste', 'actualizacion_rentas', 'residual_estatico', 'residual_dinamico')),
    valor_tasacion         numeric(14, 2),    -- valor final a efectos hipotecarios
    valor_mercado          numeric(14, 2),
    valor_hipotecario      numeric(14, 2),    -- valor hipotecario / sostenible
    valor_reposicion_bruto numeric(14, 2),
    valor_reposicion_neto  numeric(14, 2),
    valor_seguro           numeric(14, 2),
    moneda                 char(3) NOT NULL DEFAULT 'EUR',
    condicionantes         text[],
    advertencias           text[],
    -- estado del pipeline
    estado                 text NOT NULL DEFAULT 'pendiente'
                           CHECK (estado IN ('pendiente', 'extraida', 'en_revision_extraccion', 'validada_extraccion', 'puntuada', 'error')),
    extraccion_modelo      text,
    extraccion_version     text,
    extraccion_json        jsonb,             -- salida cruda del extractor, para re-procesar
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON tasacion.tasacion (sociedad_id);
CREATE INDEX ON tasacion.tasacion (tecnico_id);
CREATE INDEX ON tasacion.tasacion (operacion_id);

-- Una tasación cubre una o varias fincas (vivienda + garaje + trastero).
CREATE TABLE tasacion.finca (
    id                          bigserial PRIMARY KEY,
    tasacion_id                 bigint NOT NULL REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    orden                       smallint NOT NULL DEFAULT 1,
    tipo                        text NOT NULL CHECK (tipo IN ('vivienda', 'garaje', 'trastero', 'local', 'otro')),
    es_principal                boolean NOT NULL DEFAULT false,
    -- identificación
    ref_catastral               text,          -- 20 caracteres
    finca_registral             text,
    registro_propiedad          text,
    tomo                        text,
    libro                       text,
    folio                       text,
    idufir                      text,          -- IDUFIR / CRU
    -- localización
    direccion                   text,
    tipo_via                    text,
    nombre_via                  text,
    numero                      text,
    escalera                    text,
    planta                      text,
    puerta                      text,
    codigo_postal               char(5),
    municipio_ine               char(5),
    municipio                   text,
    provincia                   text,
    geom                        geometry(Point, 4326),
    geocodificacion_fuente      text,          -- 'informe', 'catastro', 'cartociudad'...
    -- superficies (m²), tal como las declara el informe
    sup_util_comprobada         numeric(10, 2),
    sup_construida_comprobada   numeric(10, 2),
    sup_construida_con_comunes  numeric(10, 2),
    sup_util_registral          numeric(10, 2),
    sup_construida_registral    numeric(10, 2),
    sup_catastral               numeric(10, 2),
    sup_adoptada                numeric(10, 2),
    sup_parcela                 numeric(12, 2),
    -- características
    anio_construccion           smallint,
    anio_rehabilitacion         smallint,
    dormitorios                 smallint,
    banos                       smallint,
    ascensor                    boolean,
    exterior                    boolean,
    orientacion                 text,
    estado_conservacion         text,
    calidad_constructiva        text,
    certificado_energetico      char(1),
    ocupacion                   text,          -- desocupada, ocupada por propietario, arrendada...
    proteccion_publica          boolean,       -- VPO / régimen de protección
    -- valores de la finca
    valor_unitario              numeric(12, 2), -- €/m²
    valor_finca                 numeric(14, 2),
    UNIQUE (tasacion_id, orden)
);
CREATE INDEX ON tasacion.finca (ref_catastral);
CREATE INDEX ON tasacion.finca USING gist (geom);

-- Testigos (comparables) declarados en el informe.
CREATE TABLE tasacion.testigo (
    id                    bigserial PRIMARY KEY,
    finca_id              bigint NOT NULL REFERENCES tasacion.finca(id) ON DELETE CASCADE,
    orden                 smallint NOT NULL,
    tipo_dato             text CHECK (tipo_dato IN ('oferta', 'transaccion', 'tasacion')),
    fuente                text,            -- portal, inmobiliaria, registro...
    url                   text,
    ref_anuncio           text,
    telefono_contacto     text,
    fecha_dato            date,
    direccion             text,
    codigo_postal         char(5),
    geom                  geometry(Point, 4326),
    ref_catastral         text,
    planta                text,
    sup_construida        numeric(10, 2),
    sup_util              numeric(10, 2),
    dormitorios           smallint,
    banos                 smallint,
    anio_construccion     smallint,
    estado_conservacion   text,
    precio                numeric(14, 2),
    precio_unitario       numeric(12, 2),
    coef_homogeneizacion  numeric(8, 4),  -- coeficiente total aplicado
    precio_homogeneizado  numeric(12, 2), -- €/m² tras homogeneizar
    peso                  numeric(6, 4),
    UNIQUE (finca_id, orden)
);
CREATE INDEX ON tasacion.testigo USING gist (geom);
CREATE INDEX ON tasacion.testigo (url);
CREATE INDEX ON tasacion.testigo (ref_catastral);

-- Desglose de los coeficientes de homogeneización por factor.
CREATE TABLE tasacion.testigo_coeficiente (
    testigo_id  bigint NOT NULL REFERENCES tasacion.testigo(id) ON DELETE CASCADE,
    factor      text NOT NULL,   -- superficie, ubicacion, antiguedad, estado, planta, calidad, negociacion, otro
    valor       numeric(8, 4) NOT NULL,
    PRIMARY KEY (testigo_id, factor)
);

-- Fotos del informe (y hash perceptual para detectar reciclado).
CREATE TABLE tasacion.foto (
    id           bigserial PRIMARY KEY,
    tasacion_id  bigint NOT NULL REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    pagina       smallint,
    storage_uri  text NOT NULL,
    phash        bit(64),
    descripcion  text
);
CREATE INDEX ON tasacion.foto (phash);

-- Procedencia campo a campo: de dónde salió cada valor y con qué confianza.
-- Permite resaltar en la UI el texto origen y priorizar la revisión humana.
CREATE TABLE tasacion.campo_extraido (
    id            bigserial PRIMARY KEY,
    tasacion_id   bigint NOT NULL REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    ruta          text NOT NULL,          -- JSON pointer en el esquema, p.ej. /fincas/0/sup_util_comprobada
    valor         jsonb,
    confianza     real,
    pagina        smallint,
    bbox          real[4],
    texto_origen  text,
    metodo        text,                   -- 'llm', 'regex', 'ocr+llm', 'humano'
    corregido_por text,
    corregido_en  timestamptz,
    UNIQUE (tasacion_id, ruta)
);

-- ---------------------------------------------------------------------------
-- fuente: Catastro
-- ---------------------------------------------------------------------------

-- Parcelas catastrales (INSPIRE CP). Ref. de 14 caracteres.
CREATE TABLE fuente.catastro_parcela (
    ref_catastral_14  char(14) PRIMARY KEY,
    municipio_ine     char(5),
    area_m2           numeric(14, 2),
    geom              geometry(MultiPolygon, 4326),
    raw_file_id       bigint REFERENCES ingest.raw_file(id),
    actualizado_en    date
);
CREATE INDEX ON fuente.catastro_parcela USING gist (geom);

-- Edificios (INSPIRE BU).
CREATE TABLE fuente.catastro_edificio (
    ref_catastral_14     char(14) PRIMARY KEY,
    anio_construccion    smallint,
    uso_principal        text,
    num_inmuebles        integer,
    num_viviendas        integer,
    num_plantas_sobre    smallint,
    num_plantas_bajo     smallint,
    sup_construida       numeric(14, 2),
    estado               text,
    geom                 geometry(MultiPolygon, 4326),
    raw_file_id          bigint REFERENCES ingest.raw_file(id),
    actualizado_en       date
);
CREATE INDEX ON fuente.catastro_edificio USING gist (geom);

-- Direcciones (INSPIRE AD).
CREATE TABLE fuente.catastro_direccion (
    id                bigserial PRIMARY KEY,
    ref_catastral_14  char(14),
    municipio_ine     char(5),
    tipo_via          text,
    nombre_via        text,
    numero            text,
    codigo_postal     char(5),
    geom              geometry(Point, 4326),
    raw_file_id       bigint REFERENCES ingest.raw_file(id)
);
CREATE INDEX ON fuente.catastro_direccion (ref_catastral_14);
CREATE INDEX ON fuente.catastro_direccion USING gist (geom);
CREATE INDEX ON fuente.catastro_direccion USING gin (nombre_via gin_trgm_ops);

-- Inmuebles (ref. de 20 caracteres): uso, superficie, planta. Desde servicios OVC o fichero CAT.
CREATE TABLE fuente.catastro_inmueble (
    ref_catastral_20  char(20) PRIMARY KEY,
    ref_catastral_14  char(14) NOT NULL,
    uso               text,
    sup_construida    numeric(10, 2),
    coef_participacion numeric(8, 4),
    anio_construccion smallint,
    escalera          text,
    planta            text,
    puerta            text,
    detalle           jsonb NOT NULL DEFAULT '{}',   -- construcciones, unidades constructivas
    origen            text NOT NULL CHECK (origen IN ('ovc', 'cat')),
    raw_file_id       bigint REFERENCES ingest.raw_file(id),
    consultado_en     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON fuente.catastro_inmueble (ref_catastral_14);

-- ---------------------------------------------------------------------------
-- fuente: registro
-- ---------------------------------------------------------------------------

-- Notas simples solicitadas. Los titulares van a pii.nota_simple_titular.
CREATE TABLE fuente.nota_simple (
    id                         bigserial PRIMARY KEY,
    finca_id                   bigint REFERENCES tasacion.finca(id),
    registro_propiedad         text,
    finca_registral            text,
    idufir                     text,
    fecha_emision              date,
    descripcion                text,
    sup_construida_registral   numeric(10, 2),
    sup_util_registral         numeric(10, 2),
    ref_catastral              text,
    cargas                     jsonb NOT NULL DEFAULT '[]',
    coste_eur                  numeric(8, 2),
    raw_file_id                bigint REFERENCES ingest.raw_file(id)
);

-- ---------------------------------------------------------------------------
-- fuente: estadísticas de precio (MIVAU, INE, notariado, registradores...)
-- ---------------------------------------------------------------------------

-- Formato largo para absorber ficheros heterogéneos (XLS, JSON, CSV) en una sola tabla.
CREATE TABLE fuente.estadistica (
    id            bigserial PRIMARY KEY,
    fuente        text NOT NULL,     -- 'mivau_valor_tasado', 'mivau_transacciones', 'ine_ipv', 'notariado', 'registradores_eri'
    serie         text NOT NULL,     -- identificador de la serie en origen
    ambito_tipo   text NOT NULL CHECK (ambito_tipo IN ('nacional', 'ccaa', 'provincia', 'municipio', 'distrito', 'seccion_censal', 'codigo_postal')),
    ambito_codigo text NOT NULL,
    ambito_nombre text,
    periodo_inicio date NOT NULL,
    periodicidad  text NOT NULL CHECK (periodicidad IN ('mensual', 'trimestral', 'semestral', 'anual')),
    metrica       text NOT NULL,     -- 'eur_m2', 'num_transacciones', 'indice', 'variacion_anual'...
    tipologia     text,              -- 'vivienda_libre', 'nueva', 'segunda_mano', 'piso', 'unifamiliar'...
    valor         numeric(16, 4),
    raw_file_id   bigint REFERENCES ingest.raw_file(id),
    UNIQUE (fuente, serie, ambito_tipo, ambito_codigo, periodo_inicio, metrica, tipologia)
);
CREATE INDEX ON fuente.estadistica (ambito_tipo, ambito_codigo, periodo_inicio);

-- ---------------------------------------------------------------------------
-- fuente: anuncios (scraping / datos licenciados)
-- ---------------------------------------------------------------------------

CREATE TABLE fuente.anuncio (
    id                 bigserial PRIMARY KEY,
    portal             text NOT NULL,
    id_portal          text NOT NULL,
    url                text,
    operacion          text NOT NULL DEFAULT 'venta' CHECK (operacion IN ('venta', 'alquiler')),
    tipologia          text,
    direccion          text,
    codigo_postal      char(5),
    municipio_ine      char(5),
    geom               geometry(Point, 4326),
    geom_precision     text,               -- 'exacta', 'aproximada', 'barrio'
    ref_catastral      text,
    planta             text,
    sup_construida     numeric(10, 2),
    sup_util           numeric(10, 2),
    dormitorios        smallint,
    banos              smallint,
    anio_construccion  smallint,
    estado             text,
    ascensor           boolean,
    exterior           boolean,
    certificado_energetico char(1),
    anunciante_tipo    text,               -- particular, profesional
    anunciante         text,
    primera_vez        timestamptz NOT NULL,
    ultima_vez         timestamptz NOT NULL,
    activo             boolean NOT NULL DEFAULT true,
    UNIQUE (portal, id_portal)
);
CREATE INDEX ON fuente.anuncio USING gist (geom);
CREATE INDEX ON fuente.anuncio (codigo_postal);
CREATE INDEX ON fuente.anuncio (ref_catastral);

-- Cada vez que vemos el anuncio: historia de precios y snapshot crudo.
CREATE TABLE fuente.anuncio_observacion (
    anuncio_id   bigint NOT NULL REFERENCES fuente.anuncio(id) ON DELETE CASCADE,
    observado_en timestamptz NOT NULL,
    precio       numeric(14, 2),
    datos        jsonb NOT NULL DEFAULT '{}',
    raw_file_id  bigint REFERENCES ingest.raw_file(id),
    PRIMARY KEY (anuncio_id, observado_en)
);

CREATE TABLE fuente.anuncio_foto (
    id           bigserial PRIMARY KEY,
    anuncio_id   bigint NOT NULL REFERENCES fuente.anuncio(id) ON DELETE CASCADE,
    url          text,
    storage_uri  text,
    phash        bit(64)
);
CREATE INDEX ON fuente.anuncio_foto (phash);

-- ---------------------------------------------------------------------------
-- fuente: otras
-- ---------------------------------------------------------------------------

CREATE TABLE fuente.subasta_boe (
    id                 text PRIMARY KEY,   -- identificador de subasta del BOE
    estado             text,
    fecha_inicio       date,
    fecha_fin          date,
    tipo_bien          text,
    direccion          text,
    codigo_postal      char(5),
    municipio_ine      char(5),
    ref_catastral      text,
    geom               geometry(Point, 4326),
    valor_subasta      numeric(14, 2),
    valor_tasacion     numeric(14, 2),
    puja_maxima        numeric(14, 2),
    cargas             numeric(14, 2),
    datos              jsonb NOT NULL DEFAULT '{}',
    raw_file_id        bigint REFERENCES ingest.raw_file(id)
);
CREATE INDEX ON fuente.subasta_boe (ref_catastral);
CREATE INDEX ON fuente.subasta_boe USING gist (geom);

CREATE TABLE fuente.zona_inundable (
    id               bigserial PRIMARY KEY,
    tipo             text NOT NULL,        -- 'fluvial', 'costera', 'dph'...
    periodo_retorno  smallint,             -- 10, 100, 500 años
    demarcacion      text,
    geom             geometry(MultiPolygon, 4326) NOT NULL,
    raw_file_id      bigint REFERENCES ingest.raw_file(id)
);
CREATE INDEX ON fuente.zona_inundable USING gist (geom);

CREATE TABLE fuente.certificado_energetico (
    id                 bigserial PRIMARY KEY,
    ccaa               text NOT NULL,
    num_registro       text,
    ref_catastral      text,
    direccion          text,
    letra_consumo      char(1),
    letra_emisiones    char(1),
    consumo_kwh_m2     numeric(10, 2),
    emisiones_kg_m2    numeric(10, 2),
    sup_util           numeric(10, 2),
    anio_construccion  smallint,
    fecha_emision      date,
    raw_file_id        bigint REFERENCES ingest.raw_file(id),
    UNIQUE (ccaa, num_registro)
);
CREATE INDEX ON fuente.certificado_energetico (ref_catastral);

-- ---------------------------------------------------------------------------
-- scoring
-- ---------------------------------------------------------------------------

-- Estimación independiente del valor de una finca: intervalo, no punto.
CREATE TABLE scoring.avm_estimacion (
    id              bigserial PRIMARY KEY,
    finca_id        bigint NOT NULL REFERENCES tasacion.finca(id) ON DELETE CASCADE,
    modelo          text NOT NULL,        -- 'comparables', 'hedonico', 'externo:<proveedor>'
    modelo_version  text NOT NULL,
    fecha_valor     date NOT NULL,
    eur_m2_p10      numeric(12, 2),
    eur_m2_p50      numeric(12, 2),
    eur_m2_p90      numeric(12, 2),
    valor_p10       numeric(14, 2),
    valor_p50       numeric(14, 2),
    valor_p90       numeric(14, 2),
    descuento_oferta_cierre numeric(6, 4),
    n_comparables   integer,
    detalle         jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON scoring.avm_estimacion (finca_id);

CREATE TABLE scoring.avm_comparable (
    estimacion_id     bigint NOT NULL REFERENCES scoring.avm_estimacion(id) ON DELETE CASCADE,
    anuncio_id        bigint NOT NULL REFERENCES fuente.anuncio(id),
    distancia_m       numeric(10, 1),
    similitud         real,
    precio_ajustado   numeric(12, 2),   -- €/m² tras homogeneizar y aplicar descuento
    peso              real,
    PRIMARY KEY (estimacion_id, anuncio_id)
);

-- ¿Existe el testigo declarado? Cruce contra nuestro histórico de anuncios.
CREATE TABLE scoring.verificacion_testigo (
    id             bigserial PRIMARY KEY,
    testigo_id     bigint NOT NULL REFERENCES tasacion.testigo(id) ON DELETE CASCADE,
    anuncio_id     bigint REFERENCES fuente.anuncio(id),
    resultado      text NOT NULL CHECK (resultado IN ('coherente', 'discrepante', 'no_encontrado', 'no_evaluable')),
    score_match    real,
    distancia_m    numeric(10, 1),
    diferencias    jsonb NOT NULL DEFAULT '{}',    -- {precio: {declarado, observado}, sup: {...}}
    -- otras tasaciones que reutilizan este mismo testigo
    reutilizado_en bigint[] NOT NULL DEFAULT '{}',
    version        text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON scoring.verificacion_testigo (testigo_id);

-- Resultado de cada regla aplicada a una tasación.
CREATE TABLE scoring.chequeo (
    id               bigserial PRIMARY KEY,
    tasacion_id      bigint NOT NULL REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    codigo           text NOT NULL,      -- p.ej. 'SUP_CATASTRO_DESVIO', 'ANCLAJE_PRECIO'
    categoria        text NOT NULL CHECK (categoria IN ('valor', 'calidad', 'fraude')),
    resultado        text NOT NULL CHECK (resultado IN ('ok', 'aviso', 'fallo', 'no_evaluable')),
    bloqueante       boolean NOT NULL DEFAULT false,
    severidad        real,               -- 0..1, contribución al sub-score
    valor_observado  jsonb,
    valor_esperado   jsonb,
    explicacion      text,
    evidencia        jsonb NOT NULL DEFAULT '{}',   -- ids de fuentes, raw_files, anuncios...
    version_reglas   text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON scoring.chequeo (tasacion_id);
CREATE INDEX ON scoring.chequeo (codigo, resultado);

-- Veredicto: semáforo + sub-scores.
CREATE TABLE scoring.score (
    id              bigserial PRIMARY KEY,
    tasacion_id     bigint NOT NULL REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    version         text NOT NULL,
    sub_valor       real,
    sub_calidad     real,
    sub_fraude      real,
    compuesto       real,
    veredicto       text NOT NULL CHECK (veredicto IN ('validada', 'dudas', 'revision_obligatoria')),
    motivos         jsonb NOT NULL DEFAULT '[]',   -- ordenados, con referencia a chequeo.id
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON scoring.score (tasacion_id, created_at DESC);

-- Decisión humana: etiqueta para calibrar umbrales y entrenar la v2.
CREATE TABLE scoring.revision (
    id                bigserial PRIMARY KEY,
    tasacion_id       bigint NOT NULL REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    score_id          bigint REFERENCES scoring.score(id),
    revisor           text NOT NULL,
    veredicto         text NOT NULL CHECK (veredicto IN ('validada', 'dudas', 'revision_obligatoria')),
    valor_estimado    numeric(14, 2),     -- opinión de valor del revisor, si la da
    motivos           text[],
    comentario        text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Sesgo sistemático por técnico o sociedad, con shrinkage e intervalos.
CREATE TABLE scoring.sesgo_tasador (
    id                          bigserial PRIMARY KEY,
    entidad_tipo                text NOT NULL CHECK (entidad_tipo IN ('tecnico', 'sociedad')),
    entidad_id                  bigint NOT NULL,
    periodo_inicio              date NOT NULL,
    periodo_fin                 date NOT NULL,
    n_tasaciones                integer NOT NULL,
    -- desviación vs AVM, corregida por zona y tipología (log ratio)
    desviacion_bruta            real,
    desviacion_shrunk           real,
    desviacion_ic_bajo          real,
    desviacion_ic_alto          real,
    -- anclaje al precio de compraventa
    n_con_precio                integer,
    pct_tasacion_ge_precio      real,
    pct_tasacion_en_1pct_precio real,
    -- testigos
    pct_testigos_no_encontrados real,
    pct_testigos_reutilizados   real,
    coef_homog_medio            real,
    significativo               boolean,     -- sólo se marca con n >= umbral mínimo
    modelo_version              text NOT NULL,
    computed_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entidad_tipo, entidad_id, periodo_inicio, periodo_fin, modelo_version)
);

-- ---------------------------------------------------------------------------
-- pii: datos personales con acceso restringido
-- ---------------------------------------------------------------------------

CREATE TABLE pii.tasacion_solicitante (
    tasacion_id  bigint PRIMARY KEY REFERENCES tasacion.tasacion(id) ON DELETE CASCADE,
    nombre       text,
    nif          text,
    contacto     jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE pii.nota_simple_titular (
    nota_simple_id  bigint NOT NULL REFERENCES fuente.nota_simple(id) ON DELETE CASCADE,
    orden           smallint NOT NULL,
    nombre          text,
    nif             text,
    porcentaje      numeric(6, 3),
    titulo          text,              -- pleno dominio, usufructo...
    PRIMARY KEY (nota_simple_id, orden)
);
