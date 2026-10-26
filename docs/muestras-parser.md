# Informes públicos para probar el parser

Revisión: **2026-10-26**. Hay cinco PDFs en `data/raw/tasaciones_publicas/` y cinco extracciones previas en la BD local. Los PDFs y las salidas completas quedan fuera de Git; el [manifiesto](../examples/tasaciones/muestras.json) guarda procedencia, SHA-256 y campos de referencia revisados en el documento.

## Dos documentos de procedencia oficial verificada

| Muestra | Publicación y autor | Contenido | Uso en la prueba |
|---|---|---|---|
| `coslada` | [Ministerio de Justicia / ORGA](https://www.mjusticia.gob.es/es/AreaTematica/OficinaRecuperacion/Documents/2021-10-21%20Exp-20210094%20Tasaci%C3%B3n%20finca.pdf); THIRSA para SEGIPSA | 37 páginas, vivienda en Coslada, emisión 10-09-2021, 180.025,46 €, 103 m² adoptados, seis testigos | Extracción residencial: importes, superficies, fechas, referencia catastral, testigos y páginas de evidencia |
| `valencia` | [Ayuntamiento de València](https://www.valencia.es/ayuntamiento/urbanismo2.nsf/0/6098D4F0CC8EB58CC1258B10001DFC05/%24FILE/2_PJE_Anexo2_Tasacion_PR331424CE_F_unlocked_firmado.pdf?OpenElement=); Euroval | 73 páginas, expediente 14970/2024, 21 parcelas, 1.155.057,73 €, método residual estático | Extracción de varias fincas; caso fuera del alcance residencial hipotecario del MVP |

Ambas descargas devolvieron HTTP 200, contenido PDF y exactamente el SHA-256 de las copias locales. Publicación oficial **no significa tasación hipotecaria vigente**: Coslada declara en la página 19 que se basa en la metodología ECO/805 pero no se ajusta a ella; Valencia excluye expresamente su finalidad del ámbito ECO en la página 3. No deben servir como ejemplos positivos de cumplimiento. Coslada solo tuvo visita exterior.

Las páginas del manifiesto cuentan desde la primera página física del PDF. Por ejemplo, las fechas de Coslada están en la página PDF 21, aunque el informe la numera como 20.

## Ejecutar desde la raíz del repositorio

Preparar el PDF y comprobar su integridad, sin BD ni credenciales LLM:

```bash
uv run python -m tasacion.ingesta.muestras coslada
```

El comando descarga el original si falta; si existe, comprueba su hash. Rechaza HTML servido con HTTP 200 y PDFs distintos de la referencia, sin sobrescribir una copia local distinta.

Ejecutar una extracción nueva y comprobarla (envía el PDF completo a Anthropic; usa las credenciales configuradas para el SDK):

```bash
uv run python -m tasacion.ingesta.muestras coslada --extraer
uv run python -m tasacion.ingesta.muestras valencia --extraer
```

Guarda el JSON y los metadatos en `data/raw/tasaciones_publicas/<archivo>.extraida.json`. No carga ni puntúa la tasación. Para usar directamente el parser existente:

```bash
uv run tasacion ingerir data/raw/tasaciones_publicas/segipsa_residencial.pdf --solo-json
```

Comprobar una salida existente, sin llamadas al LLM:

```bash
uv run python -m tasacion.ingesta.muestras coslada --json data/pruebas_parser/segipsa_residencial.json
uv run python -m tasacion.ingesta.muestras valencia --json data/pruebas_parser/valencia_pr331424.json
```

Las rutas `data/pruebas_parser/` contienen las extracciones exportadas de la BD en esta revisión y son locales. En otro checkout se pueden generar con `--extraer` y pasar el archivo `.extraida.json` resultante. Código de salida 0 si pasan los controles y 1 si hay discrepancias; los errores de descarga/esquema también terminan con código no cero.

## Resultado observado y límites

- Las cinco extracciones previas (`extractor-v3`) validan contra el esquema Pydantic actual.
- Coslada pasa nueve campos de referencia y dos recuentos; Valencia, seis campos y un recuento. También pasan los límites de páginas de evidencia y la coincidencia del hash de los metadatos.
- **No se ejecutó de nuevo el LLM**: esta sesión no tiene credenciales de Anthropic. Son comprobaciones sobre salidas ya almacenadas, no una nueva medición del modelo.
- Los controles no verifican todos los campos, la correspondencia literal de cada cita, la precisión OCR, las firmas digitales ni el cumplimiento normativo. Falta una muestra hipotecaria actual, anonimizada y revisada por un tasador, además de casos escaneados y documentos posteriores a la reforma de 2025.

Otros archivos locales: `segipsa_unifamiliar.pdf` (Alovera), `st_ejemplo.pdf` y `tinsa_ejemplo.pdf`. No se han añadido al manifiesto: no se ha cerrado la comprobación de procedencia y versión de sus originales. El Ministerio publica una [versión corregida de Alovera que menciona el 50 % de la finca](https://www.mjusticia.gob.es/es/AreaTematica/OficinaRecuperacion/Documents/2021-11-15%20Exp-20210094%20Tasaci%C3%B3n%20corregida%20SEGIPSA%20del%2050%20de%20Finca%20n%C2%BA%206465%20de%20Alovera_Censurada.pdf); no debe suponerse que equivale a la copia local.

Los informes públicos pueden incluir datos personales y condiciones de reproducción. Se versionan enlaces y referencias de prueba, no los informes ni las extracciones completas.
