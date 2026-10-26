# Revisión de fuentes y validación — 2026-10-26

Alcance: revisión del catálogo, descargadores, extracción y reglas; comprobación por GET de **14 URLs seleccionadas**, inventario de la BD local y contraste de dos informes con originales oficiales. No equivale a verificar todas las URLs del catálogo, todas las licencias ni la calidad de cada registro descargado.

La evidencia técnica (URL, estado, formato, tamaño y SHA-256) está en [revision-fuentes-2026-10-26.json](revision-fuentes-2026-10-26.json). Los 14 accesos respondieron HTTP 200 con el formato/estructura esperado; no se usó el estado HTTP como única prueba.

## Fuentes prioritarias

| Fuente comprobada | Resultado | Papel real en el sistema y límite |
|---|---|---|
| Catastro OVC, consulta DNPRC | JSON con `consulta_dnprcResult` | Contraste individual implementado y caché en BD. No acredita precio de compraventa ni sustituye al Registro. La caché actual no tiene caducidad automática |
| Catastro INSPIRE BU, feed nacional | XML ATOM | Descarga y transformación PostGIS implementadas; geometría y datos catastrales, no precios |
| MIVAU, `35101000.XLS` | XLS binario | Descargado; benchmarking agregado. No está conectado como regla de precio individual en `puntuar` |
| INE IPV, tabla 80270 (`nult=1`) | 240 series, 2T 2026; índice general nacional 111,095 | Ajuste temporal implementado en `scoring/ipv.py`; dato nacional/CCAA, no municipal |
| Registradores, ficha y CSV residencial | HTML de ficha y CSV con cabeceras de precios | Descargado; agregado provincial, no transacciones identificadas por inmueble |
| BOE, sumario 24-10-2026 | JSON `status`/`data` | Descarga de sumarios y anuncios administrativos; no una API del precio de adjudicación ni de todos los informes anexos |
| CartoCiudad, candidatos | Un candidato JSON | Respaldo de geocodificación de testigos; la precisión de una calle sin portal limita las reglas de distancia |
| IDEE inundaciones, GetCapabilities | XML WMS | Servicio disponible, **contraste por inmueble todavía sin integrar**. Esta revisión no ejecutó GetFeatureInfo |
| IGN PNOA, GetCapabilities | XML WMS | Disponible, todavía sin integrar. No se comprobó un GetMap |
| CEE Madrid, CKAN `package_show` | JSON de metadatos | Resolución de recursos implementada; el scoring aún no cruza certificados por inmueble |
| CEE Cataluña, Socrata (`$limit=1`) | Una fila JSON | Endpoint paginado disponible. El descargador sigue usando `rows.csv`, pese a la advertencia del catálogo: migración pendiente |
| Informes de Justicia y València | PDF, ambos idénticos al archivo local | Muestras de extracción verificadas; [procedimiento y resultados](muestras-parser.md) |

## Inventario local frente a integración

Consulta de `ingest.raw_file` el 26-10-2026: Catastro AD **7.996**, BU **8.005**, CP **8.066** archivos; MIVAU **6**; INE IPV **2**; Registradores **2**; sumarios BOE **3.467** y anuncios **39.534**. Son archivos registrados, no cobertura territorial certificada ni recuentos de inmuebles. Por eso los estados «en curso/en cola» del 24 de octubre no describen necesariamente el estado actual.

Hay CEE registrados de Madrid, Cataluña, C. Valenciana, Canarias, Euskadi y Castilla y León. También ADRH, Censo 2021, seccionado, GTFS, OSM, SERPAVI e IEE. Descargar estos archivos no significa que el AVM los utilice: el AVM v1 se basa en **anuncios de oferta**, distancia y superficie, con factor de negociación provisional 0,92. No es un modelo calibrado con precios reales de cierre.

## Normativa y muestras

La referencia debe ser el [texto consolidado ECO/805/2003](https://www.boe.es/buscar/act.php?id=BOE-A-2003-7253), seleccionando la redacción aplicable a la fecha y finalidad del informe. La [ECM/599/2025](https://www.boe.es/eli/es/o/2025/06/10/ecm599) entró en vigor el **12-08-2025** e introdujo cambios en sostenibilidad, documentación y estructura. No corresponde aplicar retrospectivamente sus nuevas exigencias a informes de 2021.

Los informes de Coslada y Valencia son públicos y auténticos en cuanto a procedencia comprobada, pero tienen finalidad de mercado/asesoramiento fuera del alcance hipotecario del MVP. No se ha validado criptográficamente ninguna firma.

## Correcciones realizadas

1. `reglas-v4` deriva a revisión los informes cuya finalidad no sea `garantia_hipotecaria`, método distinto/desconocido o finca principal no residencial. Esto incluye los ejemplos oficiales anteriores. Una finalidad hipotecaria escrita con otra etiqueta también exige revisión; no se infiere cumplimiento a partir de texto ambiguo.
2. Un resultado `no_evaluable` impide el veredicto `validada` y aparece entre los motivos. Los sub-scores siguen siendo penalizaciones por hallazgos, no medidas de cobertura ni probabilidades de fraude.
3. Añadidos manifiesto, comprobador reproducible y pruebas de regresión para los PDFs públicos. Actualizado el estado de Catastro OVC y aclarada la separación BOE IV/V-B.

Los scores guardados con versiones anteriores no se reescriben automáticamente: para un expediente concreto, ejecutar `uv run tasacion puntuar ID` genera una evaluación con la nueva versión.

Validación local: las 31 pruebas pasan con PostgreSQL disponible; el módulo de muestras tiene 98 % de cobertura. Las extracciones almacenadas de Coslada y Valencia pasan los controles del manifiesto. Se han vuelto a puntuar los expedientes locales 12, 13 y 16 (Coslada, Alovera y Valencia) con `reglas-v4`: los tres tienen `ALCANCE` bloqueante y `revision_obligatoria`. No se ha ejecutado una nueva extracción LLM.

## Pendientes concretos

- **Cumplimiento:** reglas por fecha/finalidad; la comprobación de seis meses usa todavía 183 días, una aproximación incorrecta para algunos meses. El extractor pide lagunas ECO en su prompt sin resolver primero la versión normativa aplicable. Sus avisos requieren revisión humana.
- **Fuentes ausentes o fallidas:** la protección frente a `no_evaluable` no cubre excepciones de red sin capturar; aún pueden abortar el scoring. Añadir trazabilidad temporal y caducidad a las consultas catastrales, y tratar los errores de servicio de forma distinta a una RC inexistente.
- **Estadísticas:** conectar los benchmarks MIVAU/Registradores al scoring; elegir el CSV de Registradores por fecha, no por orden lexicográfico. Migrar Cataluña al endpoint paginado y verificar formato/contenido antes de registrar cualquier descarga genérica.
- **Valor:** calibrar negociación y umbrales con operaciones y revisiones del banco; el ajuste por IPV autonómico de anuncios actuales no reconstruye un mercado local histórico. El esquema permite varias fincas, pero las reglas de valor se centran en la principal: falta validar anejos y agregación.
- **Fuentes adicionales:** integrar inundación, certificados energéticos y registro actualizado de sociedades del BdE. Disponibilidad del endpoint y cumplimiento de una obligación son comprobaciones distintas.
- **Uso comercial:** las comprobaciones HTTP no validan licencias. Mantener el histórico de condiciones y acuerdos de cada proveedor; no interpretar `robots.txt` ni una respuesta 200 como autorización de uso comercial.

La revisión deja un camino verificable de pruebas, no una certificación de que el MVP cumpla toda la normativa o esté listo para decisiones hipotecarias automáticas.
