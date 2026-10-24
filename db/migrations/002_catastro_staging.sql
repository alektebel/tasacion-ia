-- Carga de Catastro INSPIRE: tablas intermedias que rellena ogr2ogr (scripts/cargar_catastro.sh)
-- y código de municipio del Catastro, que no coincide con el código INE.

CREATE SCHEMA IF NOT EXISTS staging;

ALTER TABLE fuente.catastro_parcela   ADD COLUMN IF NOT EXISTS municipio_catastro char(5);
ALTER TABLE fuente.catastro_edificio  ADD COLUMN IF NOT EXISTS municipio_catastro char(5);
ALTER TABLE fuente.catastro_direccion ADD COLUMN IF NOT EXISTS municipio_catastro char(5);

CREATE INDEX IF NOT EXISTS catastro_parcela_mun_idx  ON fuente.catastro_parcela (municipio_catastro);
CREATE INDEX IF NOT EXISTS catastro_edificio_mun_idx ON fuente.catastro_edificio (municipio_catastro);
