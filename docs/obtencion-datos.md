# Vías de obtención de datos

Cómo entra en el sistema cada dato y en qué estado está.

- El **catálogo** de cada fuente (qué verifica, licencia, URLs probadas) está en [`fuentes.md`](fuentes.md).
- La **instalación** y los comandos de descarga están en [`instalacion.md`](instalacion.md).

Hay siete vías de obtención:

| # | Vía | Cuándo se usa | Coste |
|---|---|---|---|
| 1 | **Descarga masiva abierta** | Datos de referencia que se refrescan periódicamente | Gratis |
| 2 | **API pública por consulta** | En el momento de puntuar una tasación concreta (por ref. catastral, dirección o coordenadas) | Gratis, con límites de uso |
| 3 | **Descarga manual con identificación** | Fuentes que exigen certificado, Cl@ve o formulario | Gratis |
| 4 | **Datos del cliente** | PDFs de tasación, datos de la operación, histórico y resultados | — |
| 5 | **Generados por nosotros** | Lo que extraemos de las propias tasaciones (testigos, técnicos) | — |
| 6 | **Compra o licencia** | Datos sin alternativa abierta (precios individuales, nota simple) | De pago |
| 7 | **Scraping** | Webs sin API ni descarga | Riesgo legal; ver abajo |

---

## 1. Descarga masiva abierta

| Fuente | Formato | Comando | Refresco | Estado (2026-10-24) |
|---|---|---|---|---|
| Catastro INSPIRE: parcelas (CP) | ZIP con GML, por municipio | `tasacion descargar catastro --capa CP` | Semestral | ⏳ En curso (unos 8.000 municipios) |
| Catastro INSPIRE: edificios (BU) | ZIP con GML | `--capa BU` | Semestral | ⏳ En cola |
| Catastro INSPIRE: direcciones (AD) | ZIP con GML | `--capa AD` | Semestral | ⏳ En cola (Soria ya descargada como prueba) |
| MIVAU: valor tasado y transacciones | XLS | `tasacion descargar estadisticas` | Trimestral | ✅ 6 ficheros, 17 MB |
| INE: Índice de Precios de Vivienda (tablas 80270 y 25171) | JSON | ídem | Trimestral | ✅ 3,5 MB |
| Registradores: €/m² y compraventas por provincia | CSV (ODbL) | ídem | Trimestral | ✅ 0,6 MB |
| Certificados energéticos: Madrid, C. Valenciana, Canarias, Cataluña | CSV/ZIP | `tasacion descargar certificados` | Mensual o semestral | ✅ 1,1 GB |
| Certificados energéticos: Aragón | CSV | ídem | — | ❌ SSL roto en el servidor de origen |
| Sumarios del BOE (subastas en la sección V-B) | JSON | `tasacion descargar boe` | Diario | ⏳ En curso desde 2015 |
| Anuncios individuales de subasta del BOE | XML (`/diario_boe/xml.php?id=BOE-B-...`) | — | Diario | 🔲 Pendiente: filtrar los sumarios y bajar cada anuncio |
| Ayuntamiento de Madrid: licencias urbanísticas | CSV | — | — | 🔲 Pendiente (P2) |
| BdE: estadísticas agregadas de tasación | PDF | — | Trimestral | 🔲 Pendiente (P2, sin desglose por sociedad) |
| Registradores: Estadística Registral Inmobiliaria | PDF | — | Trimestral | 🔲 Pendiente (P2, solo PDF) |

## 2. API pública por consulta (al puntuar cada tasación)

No se descargan en bloque. Se llaman para cada finca y la respuesta se guarda en `ingest.raw_file` y en la tabla correspondiente, para no repetir la consulta.

| Fuente | Para qué | Límites | Estado |
|---|---|---|---|
| Catastro OVC (`Consulta_DNPRC`, `Consulta_DNPLOC`, `Consulta_RCCOOR`, `Consulta_CPMRC`) | Superficie, uso, año, planta y coordenadas por ref. catastral → `fuente.catastro_inmueble` | Menos de 1 petición/s. Si se abusa, el Catastro bloquea la IP unos 10 días. | 🔲 Por implementar |
| CartoCiudad (`geocoder/find`, `reverseGeocode`) | Geocodificar la dirección de la tasación y de los testigos; obtener CP y ref. catastral | Uso razonable | 🔲 Por implementar |
| IDEE WMS de inundaciones (`GetFeatureInfo`) | ¿Está la finca en zona inundable T10, T100 o T500? | — | 🔲 Por implementar |
| PNOA (WMS del IGN) | Ortofoto de la parcela para la vista de revisión | — | 🔲 Por implementar (P2) |
| Ficha de subasta del BOE (`detalleSubasta.php`) | Valor de tasación y puja de una subasta concreta | Solo consulta puntual (`robots.txt` bloquea el portal) | 🔲 Por implementar (P2) |

## 3. Descarga manual con identificación

| Fuente | Por qué es manual | Procedimiento | Estado |
|---|---|---|---|
| Catastro alfanumérico (formato CAT): todos los inmuebles con superficie, uso, planta y año | Exige certificado o Cl@ve y aceptar una licencia | Sede Electrónica del Catastro → Descarga de datos → ficheros CAT por municipio → `data/raw/catastro_cat/` | 🔲 Pendiente. **Es la fuente de mayor valor de este bloque**: evita miles de consultas a la API. |
| Zonas inundables (shapefiles SNCZI) | Formulario con token anti-automatización | `miteco.gob.es/.../zi-lamina.html` → `data/raw/snczi/` | 🔲 Opcional: el MVP usa el WMS |
| Sociedades de tasación homologadas | La web del BdE no ofrece descarga y su API no es usable | Copiar el listado a mano a `tasacion.sociedad` (son unas 30–40) | 🔲 Pendiente |

## 4. Datos del cliente (banco piloto)

| Dato | Formato esperado | Destino | Estado |
|---|---|---|---|
| PDF de cada tasación | PDF | `ingest.raw_file` → pipeline de extracción → `tasacion.*` | 🔲 Falta muestra. **Bloquea el diseño del extractor.** |
| Datos de la operación (precio de compraventa, préstamo, LTV, fecha) | CSV o JSON | `tasacion.operacion` | 🔲 Pendiente |
| Histórico de 2.000–5.000 tasaciones | PDF + CSV | ídem | 🔲 Pendiente: es la petición clave al banco |
| Resultados posteriores (impago, re-tasación, adjudicación) | CSV | `tasacion.operacion_resultado` | 🔲 Pendiente |

## 5. Generados por nosotros

Cada tasación que ingerimos alimenta bases propias que ningún proveedor tiene:

- **Base de testigos**: todos los testigos declarados en todas las tasaciones, geolocalizados. Sirve para detectar **testigos reciclados** y, con volumen, como fuente de comparables por sí misma.
- **Maestro de técnicos y sociedades**, con su historial de desviaciones (`scoring.sesgo_tasador`).
- **Hashes de fotos**, para detectar fotos reutilizadas entre tasaciones.
- **Etiquetas de revisión humana** (`scoring.revision`), para calibrar los umbrales y entrenar el modelo de la v2.

## 6. Compra o licencia

| Fuente | Qué aporta | Coste | Estado |
|---|---|---|---|
| Nota simple (Registradores) | Superficie registral, cargas y titularidad de la finca | ~9 € + IVA por finca (precio no confirmado en fuente oficial) | 🔲 Pedirla solo para las tasaciones 🟡 y 🔴. ¿Hay API para empresas? **No verificado.** |
| API de Idealista | Anuncios para comparables y verificación de testigos | Solicitud previa; cuotas sin verificar | 🔲 **Recomendado pedir acceso ya** |
| idealista/data, Brainsre | Histórico de ofertas y precios por zona | Bajo presupuesto | 🔲 Pedir presupuesto |
| AVM de terceros (Tinsa Digital, Gesvalt, Sociedad de Tasación) | Valor de referencia para comparar con el nuestro | Bajo presupuesto | ⚠️ Son también sociedades de tasación: hay **conflicto de interés** si se usan para juzgar sus propias tasaciones o las de su competencia |

## 7. Scraping

**No se ha scrapeado ningún portal ni web privada.** Todo lo descargado viene de descargas o APIs abiertas oficiales.

| Web | Situación | Estado |
|---|---|---|
| Idealista | Sus condiciones prohíben el scraping expresamente | ⛔ Bloqueado, pendiente de decisión |
| Fotocasa, Habitaclia, pisos.com | Protegen sus contenidos y su base de datos (derecho *sui generis*, art. 133 LPI) | ⛔ Bloqueado, pendiente de decisión |
| Portal Estadístico Notarial | Sus condiciones prohíben el uso comercial y cargar los datos en una base de datos | ⛔ Excluido, pendiente de confirmación |
| subastas.boe.es | `robots.txt` con `Disallow: /` | ⛔ Se usa la API de datos abiertos del BOE en su lugar |

Si se decide scrapear portales para I+D, el diseño ya lo soporta (`fuente.anuncio` y `fuente.anuncio_observacion`). La decisión tiene que tomarla el equipo, idealmente con asesoría legal, porque el banco cliente preguntará por la procedencia de los datos.
