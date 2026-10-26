# Fuentes para validar tasaciones

Estado de implementación según la [revisión del 26-10-2026](revision-fuentes.md).

La validación combina tres tipos de evidencia: datos del inmueble, precios de mercado y requisitos normativos. Cada fuente permite comprobar una parte del informe; ninguna valida por sí sola toda la tasación.

## Qué comprueba cada fuente

| Fuente | Qué permite comprobar | Estado en el proyecto |
|---|---|---|
| **Catastro — OVC e INSPIRE** | Referencia catastral, ubicación, uso, superficie, antigüedad y geometría de parcela/edificio; coherencia de los testigos con los inmuebles de su parcela | Integrado. No acredita el precio de una compraventa ni sustituye al Registro |
| **CartoCiudad — IGN/CNIG** | Direcciones y coordenadas para situar los testigos y calcular su distancia al inmueble | Integrado como respaldo de la geocodificación catastral |
| **INE — Índice de Precios de Vivienda (IPV)** | Evolución temporal de precios para ajustar la comparación entre fechas | Integrado. Resolución nacional/autonómica; no describe por sí solo el mercado de un barrio |
| **Anuncios inmobiliarios — Fotocasa y pisos.com** | Precios de oferta de inmuebles próximos y de superficie similar para la estimación de valor del AVM | Integrados para I+D. El uso comercial requiere derechos adecuados sobre los datos; son precios de oferta, no de cierre |
| **MIVAU** | Valor tasado medio por m² y volumen de transacciones por municipio/provincia, según la serie | Datos descargados; contraste estadístico en el scoring pendiente |
| **Registradores — estadísticas abiertas** | Precios y compraventas agregados por provincia, incluidos vivienda, garaje y trastero | Datos descargados; integración como contraste pendiente. No identifican transacciones de inmuebles individuales |
| **Registro de la Propiedad — nota simple** | Descripción registral, titularidad, cargas y derechos sobre la finca | Documento que puede aportar el cliente o solicitarse por finca; contraste independiente automatizado pendiente |
| **Registros autonómicos de certificados energéticos** | Calificación energética y características asociadas al inmueble, enlazables por referencia catastral cuando está disponible | Datos descargados de varias CCAA; cruce con el expediente pendiente |
| **MITECO / SNCZI, vía IDEE** | Exposición del inmueble a zonas inundables | Servicio verificado; consulta por inmueble e integración pendientes |
| **Banco de España — registro de sociedades de tasación** | Inscripción de la sociedad tasadora y correspondencia con su código BdE | Verificación automatizada pendiente |

«Descargado» significa que hay archivos de esa fuente en el almacén local. «Integrado» significa que existe código que utiliza la fuente en el flujo de contraste o estimación; no implica cobertura completa ni un modelo ya calibrado.

Las URLs, condiciones de acceso, granularidad y licencias recogidas están en el [catálogo detallado](fuentes.md). Las [vías de obtención](obtencion-datos.md) explican cómo conseguir los datos.

## Normativa y documentos del expediente

La [Orden ECO/805/2003](https://www.boe.es/buscar/act.php?id=BOE-A-2003-7253) y sus modificaciones proporcionan los criterios normativos. Hay que seleccionar la redacción aplicable a la fecha y finalidad del informe; la [ECM/599/2025](https://www.boe.es/eli/es/o/2025/06/10/ecm599) es una de esas modificaciones. La cobertura automática de estos requisitos sigue siendo parcial.

Para contrastar el inmueble concreto, los documentos principales son la **nota simple**, la **información catastral descriptiva y gráfica** y el **certificado de eficiencia energética**. Pueden formar parte de los anexos de la tasación o llegar por separado del cliente.

El propio informe aporta superficies, valores, testigos, coeficientes, fechas, condicionantes y advertencias. El parser los extrae con citas de página para comprobar coherencia interna. Extraer una afirmación del informe no equivale a corroborarla con una fuente independiente.

## La principal carencia: precios reales de cierre

Las fuentes públicas utilizadas ofrecen estadísticas agregadas; los portales ofrecen precios anunciados. Actualmente no tenemos una fuente integrada de **precios reales de compraventa de inmuebles individuales comparables**.

Para reforzar la validación del valor necesitamos datos de transacciones con licencia o el histórico de operaciones cerradas del banco. Esos datos, junto con las revisiones de tasadores, permitirían calibrar el descuento entre oferta y cierre y los umbrales de desviación del AVM. El factor de negociación actual es provisional.

Los anuncios de subastas del BOE aportan contexto adicional, pero los valores de tasación o de salida de una subasta no deben tratarse como precios de compraventa ordinaria.

## Documentos para probar la extracción

Hay [informes publicados por el Ministerio de Justicia y el Ayuntamiento de València](muestras-parser.md), con enlaces oficiales, hashes y campos de referencia. Sirven para probar el parser. Los dos originales verificados tienen finalidades fuera del alcance hipotecario del MVP, por lo que no son ejemplos positivos de cumplimiento ECO ni referencias para calibrar el precio de cierre.
