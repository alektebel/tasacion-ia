-- Geolocalización de testigos (tasacion/geocodificar.py): de dónde sale el punto y con qué
-- precisión, la dirección normalizada y la parcela catastral a la que se ha casado.

ALTER TABLE tasacion.testigo ADD COLUMN IF NOT EXISTS geocodificacion_fuente    text;  -- catastro_rc | catastro_direccion | cartociudad
ALTER TABLE tasacion.testigo ADD COLUMN IF NOT EXISTS geocodificacion_precision text;  -- parcela | portal | calle
ALTER TABLE tasacion.testigo ADD COLUMN IF NOT EXISTS direccion_normalizada     jsonb;
ALTER TABLE tasacion.testigo ADD COLUMN IF NOT EXISTS ref_catastral_14_geo      char(14);

-- El geocodificador local filtra primero por CP y después compara nombres de vía.
CREATE INDEX IF NOT EXISTS catastro_direccion_cp_idx ON fuente.catastro_direccion (codigo_postal);
