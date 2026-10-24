#!/usr/bin/env bash
# Carga los ZIP de Catastro INSPIRE descargados en tablas staging.* con ogr2ogr (GDAL en
# Docker) y después los pasa a fuente.catastro_* con db/transform/catastro.sql.
#
#   scripts/cargar_catastro.sh            # toda España
#   scripts/cargar_catastro.sh 42         # sólo la gerencia/provincia 42
#
# Reproyecta a EPSG:4326 (cada ZIP declara su huso UTM, Canarias incluida).
# De las parcelas sólo carga las urbanas: la ref. catastral rústica no tiene letras en las
# posiciones 6-7 de la hoja (PPMMMAPPPPPPPP) y no aporta nada a la valoración de vivienda.
set -euo pipefail
cd "$(dirname "$0")/.."

PROVINCIA=${1:-}
PARALELO=${PARALELO:-4}
GDAL_IMAGE=ghcr.io/osgeo/gdal:ubuntu-small-3.10.0
PG="PG:host=localhost port=5433 dbname=tasacion user=tasacion password=${POSTGRES_PASSWORD:-tasacion}"
DATA=$PWD/data

psql_() { docker compose exec -T db psql -v ON_ERROR_STOP=1 -U tasacion -d tasacion "$@"; }

psql_ -f - < db/migrations/002_catastro_staging.sql
psql_ -c "DROP TABLE IF EXISTS staging.cp, staging.bu, staging.ad, staging.ad_via, staging.ad_cp"

# Script que corre dentro del contenedor GDAL para un ZIP: capa -> tabla staging.
cat > "$DATA/.cargar_zip.sh" <<'EOF'
#!/bin/sh
set -e
zip=$1; pg=$2
base=$(basename "$zip" .zip)          # A.ES.SDGC.CP.42001
capa=$(echo "$base" | cut -d. -f4)    # CP | BU | AD
mun=$(echo "$base" | cut -d. -f5)     # 42001
opts="-append -t_srs EPSG:4326 -lco SPATIAL_INDEX=NONE -lco GEOMETRY_NAME=geom -dialect SQLite --config PG_USE_COPY YES"
case $capa in
CP)
  ogr2ogr $opts -nln staging.cp -nlt MULTIPOLYGON "$pg" "/vsizip/$zip/$base.cadastralparcel.gml" \
    -sql "SELECT nationalCadastralReference AS rc, areaValue AS area, '$mun' AS mun, geometry FROM CadastralParcel
          WHERE substr(nationalCadastralReference, 8, 2) GLOB '[A-Z][A-Z]'" ;;
BU)
  ogr2ogr $opts -nln staging.bu -nlt MULTIPOLYGON "$pg" "/vsizip/$zip/$base.building.gml" \
    -sql "SELECT reference AS rc, beginning, currentUse AS uso, conditionOfConstruction AS estado,
                 numberOfBuildingUnits AS inmuebles, numberOfDwellings AS viviendas, value AS sup,
                 '$mun' AS mun, geometry FROM Building" ;;
AD)
  f="/vsizip/$zip/$base.gml"
  ogr2ogr $opts -nln staging.ad -nlt POINT --config GML_ATTRIBUTES_TO_OGR_FIELDS YES "$pg" "$f" \
    -sql "SELECT localId AS id, designator AS numero, component_href AS comp, '$mun' AS mun, geometry FROM Address"
  ogr2ogr -append -dialect SQLite --config PG_USE_COPY YES -nln staging.ad_via "$pg" "$f" \
    -sql "SELECT gml_id AS id, text AS nombre FROM ThoroughfareName"
  ogr2ogr -append -dialect SQLite --config PG_USE_COPY YES -nln staging.ad_cp "$pg" "$f" \
    -sql "SELECT gml_id AS id, postCode AS cp FROM PostalDescriptor" ;;
esac
EOF
chmod +x "$DATA/.cargar_zip.sh"

for capa in cp bu ad; do
    patron="A.ES.SDGC.${capa^^}.${PROVINCIA}*.zip"
    mapfile -t zips < <(find "data/raw/catastro_inspire_$capa" -name "$patron" | sort)
    echo "$(date -Is) $capa: ${#zips[@]} ficheros"
    [ ${#zips[@]} -eq 0 ] && continue
    # El primero en serie (crea la tabla), el resto en paralelo con -append.
    printf '%s\n' "${zips[@]}" | sed 's|^data/|/data/|' | {
        read -r primero
        docker run --rm --network host -v "$DATA:/data:ro" $GDAL_IMAGE /data/.cargar_zip.sh "$primero" "$PG"
        docker run --rm -i --network host -v "$DATA:/data:ro" $GDAL_IMAGE \
            sh -c "xargs -P $PARALELO -I{} /data/.cargar_zip.sh {} '$PG' 2>&1 | grep -vE 'Warning 1|being appended to' || true"
    }
done

echo "$(date -Is) transformando a fuente.catastro_*"
psql_ -f - < db/transform/catastro.sql
echo "$(date -Is) hecho"
