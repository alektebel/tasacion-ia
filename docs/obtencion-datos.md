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
| Anuncios de subasta administrativa del BOE (sección V-B: Seguridad Social, Hacienda, Defensa) | XML (`/diario_boe/xml.php?id=BOE-B-...`), con ref. catastral y m² | `tasacion descargar boe-subastas` | Diario | ⏳ En curso (unos 15.000) |
| Subastas judiciales del BOE (sección IV) | El BOE solo publica el id `SUB-JA-…`; el valor está en subastas.boe.es (bloqueado por robots.txt) | — | — | ⛔ Solo el identificador |
| INE, renta por sección censal (ADRH, 2015–2024) | CSV | `tasacion descargar abiertos --fuente ine_adrh` | Anual | ⏳ 54 tablas |
| INE, cartografía de secciones censales 2026 | SHP en ZIP | `--fuente ine_seccionado` | Anual | ⏳ |
| INE, Censo 2021 (indicadores por sección, año de construcción por municipio, microdatos de viviendas) | CSV, XLSX, ZIP | `--fuente ine_censo2021` | — | ⏳ |
| SERPAVI: índice de alquiler por sección censal (2011–2024) | XLSX | `--fuente serpavi` | Anual | ⏳ |
| OpenStreetMap España (Geofabrik) | PBF, 1,5 GB, ODbL | `--fuente osm` | Diario | ⏳ |
| GTFS: unos 120 operadores (Mobility Database), EMT, CRTM, Cercanías | ZIP | `--fuente gtfs` | Variable | ⏳ |
| Hacienda: IRPF por municipio (2016–2023) | XLSX (sin código INE: el cruce es por nombre) | `--fuente hacienda_irpf` | Anual | ⏳ |
| Registradores: compraventas comerciales por provincia | CSV | `--fuente registradores` | Trimestral | ⏳ |
| ITE de Euskadi (un registro por edificio: año, rehabilitación, estado de la inspección) | JSON | `--fuente ite_euskadi` | — | ⏳ |
| IEE de la C. Valenciana (informes con ref. catastral y letra energética; edificios de más de 50 años) | CSV vía WFS | `--fuente iee_valencia` | — | ⏳ |
| Certificados energéticos de Euskadi y Castilla y León | CSV | `--fuente cee_euskadi cee_castilla_leon` | — | ⏳ |
| Madrid: indicadores por distrito y barrio, edificios en ruina | CSV, XLSX | `--fuente madrid_opendata` | Anual | ⏳ |
| Barcelona: valores catastrales por sección, compraventas notariales por barrio | CSV | `--fuente barcelona_opendata` | Mensual o anual | ⏳ |
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

El equipo decidió (2026-10-24) scrapear portales **solo para I+D**. En producción hay que sustituirlo por datos licenciados, porque el banco preguntará por la procedencia.

Reglas de los scrapers:
- Respetan `robots.txt`.
- Hacen una petición por segundo, sin paralelismo.
- Se paran ante un 403 o 429.
- **No intentan evadir ninguna protección anti-bot** (ni proxies, ni resolución de CAPTCHA, ni navegadores camuflados).
- Guardan el HTML en gzip en `data/raw/` para poder volver a procesarlo.

| Web | Qué se obtiene | Comando | Estado |
|---|---|---|---|
| fotocasa.es | Listado nacional, unos 484.000 anuncios. El JSON incluye coordenadas, dirección, CP, precio y características: no hace falta visitar las fichas. | `tasacion scrapear fotocasa` | ⏳ En curso. El orden de las páginas no es estable: repetir la ejecución completa los huecos. |
| pisos.com | Fase 1: listados (precio, m², habitaciones, URL), bajando por subzonas por el límite de 100 páginas. Fase 2: fichas (coordenadas, superficie útil, planta, antigüedad, conservación). | `tasacion scrapear pisoscom listados` y después `fichas` | ⏳ En curso; las fichas tardarán días |
| Idealista | Responde 403 (protección anti-bot) | — | ⛔ Solo vía API oficial (pedir acceso en developers.idealista.com) |
| Habitaclia | Carga los anuncios por JavaScript; es del mismo grupo que Fotocasa | — | ⏸️ No se ha hecho: aportaría poco |
| Portal Estadístico Notarial | Sus condiciones prohíben el uso comercial y cargar los datos en una base de datos | — | ⛔ Excluido |
| subastas.boe.es | `robots.txt` con `Disallow: /` | — | ⛔ Se usa la API de datos abiertos del BOE |
| Subastas de la AEAT (`bienes.js`: 176 inmuebles con valoración, ref. catastral y GPS; licencia CC BY 4.0) | `robots.txt` con `Disallow: /` | — | ⛔ Pendiente de pedir permiso a la AEAT o confirmar que se puede usar |

## 8. No descargables automáticamente

| Fuente | Motivo | Alternativa |
|---|---|---|
| CNIG (CartoCiudad masivo, SIOSE, CORINE) | Las descargas exigen reCAPTCHA | Descarga manual por provincia, o WMS de ocupación del suelo en IDEE por punto |
| NAP de transporte (todos los GTFS oficiales) | Necesita API key (registro gratuito) | Registrarse y añadir la key. Mientras tanto se usa Mobility Database. |
| Ministerio del Interior: criminalidad por municipio | Protección de Cloudflare (403) | Descarga manual desde el navegador |
| Mapas de ruido (SICA, fase 3) | El servidor tiene la cadena TLS incompleta. Además, la fase 4 no está publicada. | Descarga manual, o WMS de ruido por punto |
| Certificados energéticos de Aragón | Certificado SSL roto en el servidor | Descarga manual |
| Certificados de Galicia y Castilla-La Mancha | El enlace devuelve HTML o no conecta | — |
| Certificados de Asturias, Extremadura y Cantabria | Existen (XLSX, XLS, 7z), pero falta la URL directa verificada | Pendiente |
