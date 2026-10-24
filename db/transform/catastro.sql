-- staging.* (ogr2ogr) -> fuente.catastro_*. Idempotente: reemplaza los municipios cargados.

BEGIN;

-- Parcelas urbanas
DELETE FROM fuente.catastro_parcela p USING (SELECT DISTINCT mun FROM staging.cp) s
WHERE p.municipio_catastro = s.mun;
INSERT INTO fuente.catastro_parcela (ref_catastral_14, municipio_catastro, area_m2, geom, actualizado_en)
SELECT DISTINCT ON (rc) rc, mun, area, ST_Multi(geom), current_date
FROM staging.cp
WHERE rc IS NOT NULL
ORDER BY rc
ON CONFLICT (ref_catastral_14) DO UPDATE SET
    municipio_catastro = EXCLUDED.municipio_catastro, area_m2 = EXCLUDED.area_m2,
    geom = EXCLUDED.geom, actualizado_en = EXCLUDED.actualizado_en;

-- Edificios. `beginning` es la fecha de construcción (AAAA-01-01T00:00:00).
DELETE FROM fuente.catastro_edificio e USING (SELECT DISTINCT mun FROM staging.bu) s
WHERE e.municipio_catastro = s.mun;
INSERT INTO fuente.catastro_edificio
    (ref_catastral_14, municipio_catastro, anio_construccion, uso_principal, num_inmuebles,
     num_viviendas, sup_construida, estado, geom, actualizado_en)
SELECT DISTINCT ON (rc) rc, mun,
       CASE WHEN beginning ~ '^[0-9]{4}' THEN substr(beginning, 1, 4)::smallint END,
       uso, inmuebles, viviendas, sup, estado, ST_Multi(geom), current_date
FROM staging.bu
WHERE rc IS NOT NULL
ORDER BY rc, sup DESC NULLS LAST
ON CONFLICT (ref_catastral_14) DO UPDATE SET
    municipio_catastro = EXCLUDED.municipio_catastro, anio_construccion = EXCLUDED.anio_construccion,
    uso_principal = EXCLUDED.uso_principal, num_inmuebles = EXCLUDED.num_inmuebles,
    num_viviendas = EXCLUDED.num_viviendas, sup_construida = EXCLUDED.sup_construida,
    estado = EXCLUDED.estado,
    geom = EXCLUDED.geom, actualizado_en = EXCLUDED.actualizado_en;

-- Direcciones: localId = PP.MMM.VIA.NUMERO.RC14; comp = {#PD..., #TN..., #AU...}
DELETE FROM fuente.catastro_direccion d USING (SELECT DISTINCT mun FROM staging.ad) s
WHERE d.municipio_catastro = s.mun;
WITH ad AS (
    SELECT a.*, split_part(a.id, '.', 5) AS rc,
           (SELECT substr(c, 2) FROM unnest(string_to_array(trim(both '(){}' FROM regexp_replace(a.comp::text, '^\(\d+:', '')), ',')) c WHERE c LIKE '#ES.SDGC.TN.%' LIMIT 1) AS via_id,
           (SELECT substr(c, 2) FROM unnest(string_to_array(trim(both '(){}' FROM regexp_replace(a.comp::text, '^\(\d+:', '')), ',')) c WHERE c LIKE '#ES.SDGC.PD.%' LIMIT 1) AS cp_id
    FROM staging.ad a
)
INSERT INTO fuente.catastro_direccion
    (ref_catastral_14, municipio_catastro, tipo_via, nombre_via, numero, codigo_postal, geom)
SELECT NULLIF(ad.rc, ''), ad.mun,
       split_part(v.nombre, ' ', 1),
       substr(v.nombre, length(split_part(v.nombre, ' ', 1)) + 2),
       ad.numero,
       lpad(c.cp::text, 5, '0'),
       ad.geom
FROM ad
LEFT JOIN (SELECT DISTINCT ON (id) id, nombre FROM staging.ad_via ORDER BY id) v ON v.id = ad.via_id
LEFT JOIN (SELECT DISTINCT ON (id) id, cp FROM staging.ad_cp ORDER BY id) c ON c.id = ad.cp_id;

COMMIT;

ANALYZE fuente.catastro_parcela;
ANALYZE fuente.catastro_edificio;
ANALYZE fuente.catastro_direccion;
