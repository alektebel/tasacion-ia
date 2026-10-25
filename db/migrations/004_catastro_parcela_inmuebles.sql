-- Caché del listado de inmuebles de una parcela (OVC Consulta_DNPRC con la RC de 14): uso,
-- superficie, planta y año de cada uno, en una sola llamada por parcela. Se usa para contrastar
-- los testigos (scoring/testigos_catastro.py) sin consultar inmueble a inmueble.

CREATE TABLE IF NOT EXISTS fuente.catastro_parcela_inmuebles (
    ref_catastral_14 char(14) PRIMARY KEY,
    inmuebles        jsonb NOT NULL,          -- [] si la parcela no existe
    consultado_en    timestamptz NOT NULL DEFAULT now()
);

