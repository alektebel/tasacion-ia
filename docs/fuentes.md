# Catálogo de fuentes externas para validar tasaciones (ECO/805/2003)

Para una explicación breve de qué comprueba cada fuente y cuáles están integradas, ver [fuentes de validación](fuentes-validacion.md).

Catálogo histórico del **2026-10-24**: los estados ✅ y las mediciones de este documento corresponden a esa revisión. La [revisión del 26-10-2026](revision-fuentes.md) vuelve a comprobar 14 URLs seleccionadas, distingue descarga de integración y registra las limitaciones encontradas. No se han vuelto a comprobar todas las URLs ni licencias de este catálogo. Lo marcado como **NO VERIFICADO** debe confirmarse antes de construir un descargador sobre ello.

Los documentos oficiales para ensayar la extracción están en [muestras-parser.md](muestras-parser.md), con manifiesto de procedencia y comandos reproducibles.

Convenciones:

- **✅ 200**: probado, responde y el contenido es el esperado.
- **⚠️**: responde, pero con matices (requiere cabecera `User-Agent` de navegador, formulario, login, etc.).
- **❌**: probado y no funciona desde un script (timeout, 400, 403...).
- **NO VERIFICADO**: no se ha podido comprobar.
- Prioridad MVP: **P0** = imprescindible en el MVP, **P1** = deseable en el MVP, **P2** = después del MVP o de pago.

Nota general sobre WAF: varios servidores públicos (MIVAU, `opendata.registradores.org`, BdE, BOE) rechazan peticiones con el `User-Agent` por defecto de curl o python-requests (403 o "Request Rejected"). Hay que enviar un `User-Agent` de navegador y, por cortesía, identificar el proyecto con un email de contacto en una cabecera `From`.

---

## Tabla resumen

| # | Fuente | Qué verifica de la tasación | Acceso | Formato | Granularidad | Frecuencia | Tamaño | Coste | Prioridad |
|---|---|---|---|---|---|---|---|---|---|
| 1a | Catastro OVC (servicios web por RC, dirección o coordenadas) | Ref. catastral, dirección, uso, superficie construida, año de construcción, coef. de participación, distribución por plantas | ✅ JSON y XML, sin registro | JSON / XML | Inmueble (RC de 20 caracteres) | Continua | ~2–10 KB por consulta | Gratis | **P0** |
| 1b | Catastro INSPIRE ATOM (BU, CP, AD) | Geometría de la parcela y del edificio, nº de viviendas, plantas, año, uso, superficie del edificio y dirección postal | ✅ descarga directa | GML 3.2 en ZIP, EPSG:25830 | Municipio | Semestral aprox. (última: 2026-08-21) | Provincia de Madrid: BU 439 MB, CP 326 MB, AD 34 MB. España: BU 6,5 GB, CP 14,3 GB, AD 0,7 GB (ZIP) | Gratis, con atribución | **P0** |
| 1c | Catastro descarga masiva alfanumérica (formato CAT) | Todos los datos no protegidos de cada inmueble (construcciones, usos, superficies, tipologías constructivas), sin titular ni valor | ⚠️ Sede con certificado o Cl@ve más aceptación de licencia | Texto de ancho fijo (.CAT) | Municipio o provincia | Semestral (NO VERIFICADO) | NO VERIFICADO | Gratis | **P1** |
| 1d | Valor de referencia catastral | Contraste del valor de tasación con el valor de referencia fiscal | ⚠️ Solo consulta individual en la Sede, con identificación | Web / PDF | Inmueble | Anual | — | Gratis | P1 (manual) |
| 2 | MIVAU: valor tasado de vivienda libre | Benchmark de €/m² tasado por municipio y trimestre (sesgo de la tasadora frente a la media del mercado de tasaciones) | ✅ XLS directo | XLS (BIFF8) | Municipios >25.000 hab. (306 con dato), provincia y CCAA | Trimestral (último: 2T 2026) | 0,1–4 MB por fichero | Gratis | **P0** |
| 2b | MIVAU: transacciones inmobiliarias | Liquidez y volumen del mercado local; valor medio por transacción (provincia) | ✅ XLS directo | XLS | Todos los municipios (número); provincia (importes) | Trimestral | 0,15–6,4 MB | Gratis | **P0** |
| 3 | INE IPV y ETDP | Actualización temporal de los testigos (deflactar o indexar) | ✅ API JSON `wstempus` | JSON | CCAA (IPV) | Trimestral | <100 KB | Gratis | **P0** |
| 4 | Portal Estadístico Notarial | €/m² de compraventas escrituradas por CP o municipio | ⚠️ Solo web; sin API ni CSV público | Web | Hasta código postal | Mensual | — | Gratis, **uso comercial prohibido** | P2 (solo consulta manual) |
| 5a | Registradores Open Data (CORPME) | €/m² registrado de vivienda, garaje y trastero por provincia | ✅ CSV, XLSX y ODS directos (necesita UA de navegador) | CSV `;` | Provincia y trimestre | Trimestral (último: 2T 2026) | 577 KB | Gratis, ODbL 1.0 | **P0** |
| 5b | Registradores ERI | Precios, superficies, IPVVR | ✅ PDF | PDF | CCAA y provincia | Trimestral y anual | ~1–5 MB | Gratis | P2 |
| 5c | Nota simple registral | Titularidad, cargas, superficie registral, IDUFIR, coincidencia de la finca | ⚠️ Online en la Sede de Registradores, con pago por finca | PDF | Finca | Bajo demanda | — | ~9 € + IVA por finca (NO VERIFICADO oficialmente) | P1 (por expediente) |
| 6a | BdE: registro de sociedades de tasación | Que la tasadora esté homologada y su código BdE | ⚠️ App web (Angular) y API JSON no documentada | Web / JSON | Entidad | Diaria (última publicación: 2026-10-23) | — | Gratis | **P0** (lista estática) |
| 6b | BdE: estadísticas de tasación (cap. 9 del Boletín Estadístico) | Volumen agregado del sector (no por tasadora) | ✅ PDF | PDF | Nacional, CCAA y tamaño de municipio | Anual o semestral | ~5–10 KB | Gratis | P2 |
| 7 | SNCZI zonas inundables (MITECO / IDEE) | Riesgo de inundación T10/T100/T500 del inmueble (condicionante o advertencia) | ✅ WMS (IDEE) con GetFeatureInfo; shapefiles mediante formulario web | WMS / SHP | Punto / lámina | Revisiones periódicas | SHP: T10 834 MB, T50 504 MB, T100 0,98 GB | Gratis, con atribución | **P0** (WMS por punto) |
| 8 | BOE subastas | Precio de salida y valor de tasación en subastas como testigos a la baja; alertas | ⚠️ `robots.txt: Disallow: /`. La API de datos abiertos del BOE sí está permitida | HTML / JSON / XML | Subasta o lote | Diaria | — | Gratis | P1 (vía API del BOE) |
| 9 | Portales (Idealista, Fotocasa, Habitaclia, pisos.com) | Testigos de oferta (comparables) | ⚠️ Las condiciones prohíben el scraping (expreso en Idealista). API de Idealista con solicitud previa | HTML / JSON | Anuncio | Diaria | — | API: NO VERIFICADO; productos de datos de pago | P2 (licenciar) |
| 10 | Certificados de eficiencia energética (Madrid, Cataluña, C. Valenciana, Canarias; Aragón NO VERIFICADO) | Calificación energética, año, superficie, ref. catastral (cruce con la tasación) | ✅ CSV, ZIP y API Socrata | CSV | Certificado (con RC) | Mensual o semestral | Madrid ~260 MB, Cataluña 1,34 M filas, C. Valenciana ~157 MB, Canarias 139 MB | Gratis (CC-BY u otra) | **P1** |
| 11a | CartoCiudad (CNIG) | Normalizar la dirección → coordenadas, CP y **ref. catastral de parcela** | ✅ API REST JSON | JSON | Portal | Continua | — | Gratis | **P0** |
| 11b | Ayto. Madrid open data | Catálogo de edificios protegidos, licencias urbanísticas | ✅ ZIP/CSV/XLSX | CSV, SHP | Edificio / licencia | Mensual | 1–3 MB | Gratis, CC-BY 4.0 | P1 |
| 11c | INE ADRH (renta por sección censal) | Calidad de la ubicación (variable del AVM) | ✅ API `wstempus` | JSON | Sección censal | Anual | — | Gratis | P1 |
| 11d | IGN/CNIG (PNOA WMS, centro de descargas) | Ortofoto para revisar fotos y entorno | ✅ WMS | WMS / GeoTIFF | — | — | — | Gratis | P2 |

---

## 1. Catastro (Dirección General del Catastro, DGC)

Ámbito: **todo el territorio nacional salvo País Vasco y Navarra** (catastros forales). Lo confirma literalmente la Sede: *"la totalidad del territorio nacional salvo País Vasco y Navarra"*. El feed ATOM de la DGC enlaza también los feeds forales de Álava (`geo.araba.eus`), Bizkaia (`apli.bizkaia.eus`), Gipuzkoa (`b5m.gipuzkoa.eus`) y Navarra (`filescartografia.navarra.es`), cada uno con su propia estructura.

### 1a. Servicios web gratuitos (OVC, Oficina Virtual del Catastro)

**Qué verifica:** referencia catastral (RC), dirección normalizada, uso principal (`luso`), superficie construida (`sfc`), año de construcción (`ant`), coeficiente de participación (`cpt`) y desglose de construcciones por planta y puerta (`lcons`: uso, superficie, tipología). Es el contraste directo de los campos de identificación y superficie de la tasación. Solo da datos **no protegidos**: ni titular ni valor catastral.

Endpoints probados (✅ 200; JSON con `.svc/json/` y XML con `.asmx`):

| Operación | URL (plantilla) | Estado |
|---|---|---|
| Datos por RC (14, 18 o 20 caracteres) | `https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPRC?RefCat={RC}` | ✅ 200 JSON |
| Igual, en XML | `https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC={RC}` | ✅ 200 XML |
| Datos por dirección | `https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/json/Consulta_DNPLOC?Provincia={PROV}&Municipio={MUN}&Sigla={CL}&Calle={NOMBRE}&Numero={N}` | ✅ 200 (para Alcalá 100, Madrid, devolvió 34 inmuebles) |
| Callejero | `.../COVCCallejero.svc/json/ObtenerCallejero?Provincia=MADRID&Municipio=MADRID&TipoVia=CL&NomVia=ALCALA` | ✅ 200 |
| Coordenadas → RC | `https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCoordenadas.svc/json/Consulta_RCCOOR?CoorX={x}&CoorY={y}&SRS=EPSG:25830` (también admite EPSG:4326 con X=lon, Y=lat) | ✅ 200 (si el punto cae en la calle devuelve el error 16 "no hay referencia") |
| Coordenadas → RC más cercanas | `.../COVCCoordenadas.svc/json/Consulta_RCCOOR_Distancia?CoorX=..&CoorY=..&SRS=..` | ✅ 200 |
| RC → coordenadas | `.../COVCCoordenadas.svc/json/Consulta_CPMRC?RefCat={RC14}&SRS=EPSG:4326` | ✅ 200 |
| XML de coordenadas (asmx) | `https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCoordenadas.asmx/Consulta_RCCOOR?SRS=EPSG:4326&Coordenada_X=..&Coordenada_Y=..` | ✅ 200 |
| WFS INSPIRE | `https://ovc.catastro.meh.es/INSPIRE/wfsBU.aspx?service=wfs&version=2&request=GetCapabilities` (también `wfsCP.aspx` y `wfsAD.aspx`; stored queries `GetParcel`, `GetadByRefcat` por RC) | ✅ 200 |
| WMS catastral | `https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx?SERVICE=WMS&REQUEST=GetCapabilities` | ✅ 200 |
| WMS INSPIRE | `https://ovc.catastro.meh.es/cartografia/INSPIRE/spadgcwms.aspx?service=WMS&request=GetCapabilities` | ✅ 200 |

Ejemplo de respuesta (RC `001000200VK58D`): `"debi":{"luso":"Sanidad y Beneficencia","sfc":"3860","cpt":"100,000000","ant":"1999"}` más la lista `lcons` con `{"lcd":"VIVIENDA","dfcons":{"stl":"68"},"dvcons":{"dtip":"VIVIENDA UNIFAMILIAR"}}`.

**Límites de uso:** la DGC no publica ningún límite numérico. Las condiciones de uso de la Sede (`https://www.catastro.hacienda.gob.es/ayuda/condicionesuso.htm`) dicen que se vigila el número de peticiones por IP y que, si se supera, **se deniega el servicio durante un periodo, normalmente de 10 días**. Fuentes de terceros (NO VERIFICADO) hablan de cortes tras unas 32.000 peticiones acumuladas. Recomendaciones: caché local por RC, menos de 1 petición por segundo y usar INSPIRE para cualquier operación masiva.

**Coste:** gratis, sin registro. **Licencia:** reutilización libre citando a la DGC.

**Prioridad: P0.** Es el núcleo de la verificación de superficie, uso y año.

### 1b. Descarga INSPIRE por ATOM (BU edificios, CP parcelas, AD direcciones)

**Qué verifica:** geometría de la parcela (CP), huella del edificio, `numberOfDwellings`, `numberOfBuildingUnits`, `numberOfFloorsAboveGround`, `currentUse`, `dateOfConstruction`, `officialArea` (BU) y direcciones con portal (AD). Sirve para geocodificar sin depender de servicios web y para el AVM (antigüedad y tamaño del edificio).

Feeds de nivel superior (✅ 200, actualizados a 2026-08-21):

- `https://www.catastro.hacienda.gob.es/INSPIRE/buildings/ES.SDGC.BU.atom.xml`
- `https://www.catastro.hacienda.gob.es/INSPIRE/CadastralParcels/ES.SDGC.CP.atom.xml`
- `https://www.catastro.hacienda.gob.es/INSPIRE/Addresses/ES.SDGC.AD.atom.xml`

Estructura en tres niveles:

1. El feed de nivel superior tiene una `<entry>` por **gerencia territorial** (≈ provincia; 52 de la DGC más los 4 enlaces forales). Las URLs del `<link rel="enclosure">` vienen en `http://` y hacen 302 a `https://`, así que hay que seguir redirecciones.
2. Feed por gerencia: `https://www.catastro.hacienda.gob.es/INSPIRE/buildings/{PP}/ES.SDGC.bu.atom_{PP}.xml`, `.../CadastralParcels/{PP}/ES.SDGC.CP.atom_{PP}.xml` y `.../Addresses/{PP}/ES.SDGC.AD.atom_{PP}.xml`. **Ojo: vienen en ISO-8859-1.**
3. ZIP por municipio (código de 5 dígitos con la numeración del Catastro, no la del INE; Madrid capital = `28900`):
   `https://www.catastro.hacienda.gob.es/INSPIRE/Buildings/{PP}/{PPMMM}-{NOMBRE}/A.ES.SDGC.BU.{PPMMM}.zip`
   (y su equivalente con `CadastralParcels/.../A.ES.SDGC.CP.{PPMMM}.zip` y `Addresses/.../A.ES.SDGC.AD.{PPMMM}.zip`). El nombre lleva espacios: hay que codificarlos como `%20`. Lo mejor es leer el `href` del feed en vez de construirlo.

Contenido del ZIP BU (probado con Ajalvir, 28002): `A.ES.SDGC.BU.28002.building.gml` (6 MB), `...buildingpart.gml` (11 MB), `...otherconstruction.gml` y metadatos `A.ES.SDGC.BU.MD.28002.xml`. Es GML 3.2 en EPSG:25830 (ETRS89 / UTM 30N; Canarias en otro huso).

Tamaños medidos (suma de `Content-Length` por HEAD, 2026-10-24):

| Ámbito | BU | CP | AD |
|---|---|---|---|
| Madrid capital (28900) | 116,8 MB | 40,4 MB | 7,1 MB |
| Provincia de Madrid (179 municipios) | 439 MB | 326 MB | 34 MB |
| España DGC (7.611 municipios) | **6,52 GB** | **14,29 GB** | **0,70 GB** |
| Total (DGC + 112 ZIP forales de Bizkaia) | 6,54 GB | 14,38 GB | 0,71 GB |

CP pesa más a nivel nacional por las parcelas rústicas (el ZIP más grande es el de Murcia, 44,9 MB). **El GML comprime muchísimo**: medido en Ajalvir (BU), el ZIP pesa 0,70 MB y descomprimido ocupa 17,7 MB (unas 25 veces más). No hay que descomprimir España entera en disco, que serían cientos de GB (estimación no medida). Lo razonable es procesar municipio a municipio en streaming (descargar, extraer a temporal, cargar en PostGIS con `ogr2ogr` y borrar).

**Licencia** (texto del propio feed): *"This service can be used free of charge in every instance, as long as that the D. G. of the Cadastre (Ministry of Finance) is mentioned as author and owner of the information"*. **Prioridad: P0** (al menos la provincia del piloto).

### 1c. Descarga masiva alfanumérica (formato CAT)

- Página de acceso: `https://www.sedecatastro.gob.es/Accesos/SECAccDescargaDatos.aspx` (✅ 200). Desde ahí se va a `../DescargaDatos/SECDescargaCAT.aspx`.
- Texto literal de la Sede: *"puede descargar de forma interactiva toda la información catastral de los inmuebles (salvo titularidad y valor catastral). Esta información se proporciona por municipio... **Se requiere la identificación del usuario mediante certificado electrónico o Cl@ve así como la aceptación de una licencia de uso**"*. La opción se llama "Descarga de información alfanumérica por provincia (formato CAT)".
- **Coste:** gratis (*"de forma totalmente gratuita"*, `https://www.catastro.hacienda.gob.es/ayuda/ayuda_descarga_CAT.htm`). Licencia según la Resolución de la DGC de 23-03-2011. La información es para uso propio y no puede cederse a terceros con otros fines.
- **Formato:** ficheros de texto de ancho fijo con registros de tipo 01/11/13/14/15/16/17/90, especificados en `catastro_fin_cat_2006.pdf` (el detalle de los tipos de registro no se ha verificado en esta sesión). El registro 14 (construcciones) da superficie por uso, planta y puerta, y la tipología constructiva, que es la base del valor de la construcción.
- **Automatización:** al requerir certificado o Cl@ve y una sesión interactiva, no es scriptable sin un certificado de la entidad. Se descarga a mano una vez por semestre.
- La Sede tiene además una **consulta masiva por fichero XML** de datos no protegidos, procesada fuera de línea (en torno a 1 hora). Útil para lotes de RC.
- Tamaño: NO VERIFICADO.
- **Prioridad: P1.** Mejora el detalle por planta y la tipología frente a INSPIRE.

### 1d. Valor de referencia catastral

- Es **individual y por inmueble**. Se consulta en la Sede del Catastro (`https://www.sedecatastro.gob.es/`, opción "Consulta de valor de referencia") identificándose con certificado, DNIe o Cl@ve e indicando la finalidad, la fecha y la RC. Según fuentes secundarias puede consultarlo cualquier ciudadano identificado y no solo el titular, porque no es un dato protegido como el valor catastral. **NO VERIFICADO oficialmente.**
- **No existe dataset masivo público de valores de referencia por inmueble.**
- Lo que sí es público son los **mapas de valores** (`https://www.catastro.hacienda.gob.es/ayuda/leyenda_mapavalores.htm`): por cada **Ámbito Territorial Homogéneo (ATH)** muestran el módulo de valor medio (MBR) de vivienda y garaje, el número de inmuebles y el **producto inmobiliario representativo** (tipología, superficie, calidad, antigüedad). Se publican en abierto sobre la cartografía de la Sede, navegables. **No se ha encontrado descarga en bloque ni WMS documentado (NO VERIFICADO).** Las resoluciones anuales del Informe Anual del Mercado Inmobiliario (IAMI) se publican en otoño.
- Utilidad: contraste fiscal. Si la tasación queda muy por debajo del valor de referencia, hay una incoherencia.
- **Prioridad: P1**, como consulta manual o semiautomática por expediente.

---

## 2. MIVAU: estadísticas de valor tasado y transacciones

Las estadísticas se siguen sirviendo desde el antiguo **Boletín Online de Fomento** (`apps.fomento.gob.es`). Las páginas de `mivau.gob.es` probadas dieron 403 sin UA de navegador y 404 con él.

Índices (✅ 200 con UA de navegador):

- Valor tasado: `https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=35000000`
- Transacciones: `https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=34000000`

Descarga directa, patrón `https://apps.fomento.gob.es/BoletinOnline2/sedal/{CODIGO}.XLS`. Todos ✅ 200, `application/vnd.ms-excel` y también accesibles sin UA de navegador.

### 2a. Valor tasado de vivienda (estadística basada en las tasaciones de las sociedades homologadas)

| Código | Contenido (comprobado leyendo la cabecera de la tabla) | Granularidad | Tamaño |
|---|---|---|---|
| `35101000` | Tabla 1: valor tasado medio de vivienda libre, €/m² | Nacional, CCAA, provincia | 236 KB |
| `35101500` | 1.1: vivienda libre de hasta 5 años | Ídem | 118 KB |
| `35102000` | 1.2: vivienda libre de más de 5 años | Ídem | 127 KB |
| `35102500` | 2: vivienda protegida | Ídem | 189 KB |
| `35103000` | Tabla 3: número de tasaciones usadas en el cálculo | Ídem | 158 KB |
| `35103500` | **Tabla 4: valor tasado medio de vivienda libre en municipios >25.000 hab.** (≤5 años, >5 años, total) y **número de tasaciones** | **Municipio** (306 con dato en 2T 2026) | 4 MB |

- Formato XLS (BIFF8, legible con `xlrd`). **Una hoja por trimestre** en `35103500` (`T1A2005` … `T2A2026`, 86 hojas). Las tablas provinciales agrupan cuatro años por hoja. "n.r" significa no representativo.
- Frecuencia trimestral. Último dato: **2T 2026** (fichero guardado el 2026-09-25).
- Ejemplo (2T 2026): Madrid capital, 5.418,4 €/m² en total, con 10.839 tasaciones de más de 5 años.
- **Uso:** es el benchmark directo del "valor tasado" del mismo colectivo (las tasadoras). Comparar el €/m² de cada tasación con el del municipio y trimestre, y agregar por sociedad y técnico para detectar sesgo sistemático. **Prioridad: P0.**

### 2b. Transacciones inmobiliarias (fuente: Notariado vía MIVAU)

| Código | Contenido | Granularidad |
|---|---|---|
| `34010110` | 1: número total de transacciones de vivienda | CCAA y provincia |
| `34010120` … `340101l0` | Desgloses (libre/protegida, nueva/usada, tipología, residencia del comprador) | CCAA y provincia |
| `34010210` | **2: número total de transacciones de vivienda por municipio** (6,4 MB, 8.204 filas) | **Todos los municipios** |
| `34010220` | 2.1: vivienda libre por municipio (6,4 MB) | Municipio |
| `34010230`, `34010240`, `34010250` | 2.2 protegida, 2.3 nueva, y la siguiente tabla de la serie por municipio | Municipio |
| `34020110` … `34020140` | 3.1: valor de las transacciones de vivienda libre (total, nueva, usada) | CCAA y provincia |
| `34020150` | 3.3: **valor medio** de las transacciones de vivienda libre (€) | CCAA y provincia |
| `34020160` / `34020170` | 3.3.1 / 3.3.2: valor medio, nueva / segunda mano | CCAA y provincia |
| `34020180` | 3.4: valor medio, extranjeros residentes | CCAA y provincia |

Trimestral (2004 → 2T 2026, provisional). **Prioridad: P0** para el número por municipio (liquidez), P1 para los valores medios.

---

## 3. INE: Índice de Precios de Vivienda (IPV) y ETDP

API JSON Tempus (✅ 200, sin clave):

- Operaciones: `https://servicios.ine.es/wstempus/js/ES/OPERACIONES_DISPONIBLES` (IPV: Id 15, código `IPV`; ETDP: Id 7, código `ETDP`; Hipotecas: `HPT`; ADRH: Id 353).
- Tablas de una operación: `https://servicios.ine.es/wstempus/js/ES/TABLAS_OPERACION/IPV`
- Datos: `https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/{ID}?nult={N}` (✅ 200, unos 77 KB por tabla completa con `nult=2`).

**Cambio de base:** el IPV está ya en **base 2025** con tablas nuevas. La tabla clásica 25171 (base 2015) sigue respondiendo, pero su último dato es 4T 2025.

| ID | Tabla (base 2025) | Última modificación |
|---|---|---|
| **80270** | Índices por CCAA: general, vivienda nueva y de segunda mano. Trimestrales | 2026-09-07 |
| 79563 | Índices por CCAA (mismo contenido, series `IPV1209`…) | 2026-09-07 |
| 79540 | Índices por CCAA. Medias anuales | 2026-06-08 |
| 79541 | Ponderaciones | 2026-06-08 |
| 25171 | (Base 2015, histórico) Índices por CCAA | serie cerrada |

- Último dato: 2T 2026 (Nacional, general, índice 111,095; base 2025 = 100).
- Granularidad: **solo nacional y CCAA**. No hay datos municipales.
- **Uso:** actualizar a fecha de tasación los testigos y estadísticas de otros trimestres. **Prioridad: P0**, por su bajo coste.

---

## 4. Consejo General del Notariado: Portal Estadístico Notarial

- URL: `https://www.penotariado.com/` → `https://penotariado.com/inmobiliario/home` (✅ 200). `robots.txt` devuelve 404, así que no existe.
- **Contenido:** precio medio €/m², superficie media, precio medio total y número de compraventas. Niveles: nacional, CCAA, provincia, municipio y **código postal**, además de un área dibujada en el mapa (*"siempre que los datos lo permitan"*). Actualización **mensual**.
- **Descarga o API:** no hay API ni CSV público documentado. Se pueden descargar "informes estadísticos" registrándose (gratis). La web es una app Next.js. No se ha encontrado un endpoint público documentado.
- **Condiciones** (`https://penotariado.com/inmobiliario/terminos-y-condiciones`, leído el 2026-10-24), literal:
  - *"A no utilizar el Portal Estadístico del Notariado con fines comerciales."*
  - *"...su uso exclusivo personal no permitiéndose el uso comercial de los mismos... comprometiéndose el Usuario a no incorporar dichos datos a bases de datos o ficheros informatizados..."*
  - *"queda prohibida la reproducción, distribución... de todo o parte del Servicio y/o sus contenidos, sin la previa autorización expresa del CONSEJO GENERAL DEL NOTARIADO."*
- **Conclusión:** **no se puede extraer ni incorporar a la BD del producto** sin un acuerdo con el CGN. Sí cabe la consulta manual puntual por parte del revisor. Los datos notariales agregados por municipio ya llegan por vía libre a través de MIVAU (§2b). Si se quiere el dato por CP, hay que negociar una licencia con el CGN (precio NO VERIFICADO).
- **Prioridad: P2** (o una licencia, si el presupuesto lo permite).

---

## 5. Colegio de Registradores (CORPME)

### 5a. Portal de Datos Abiertos (lo más útil)

- Portal: `https://opendata.registradores.org/` (✅ 200, CKAN sobre Liferay).
- Dataset: "Compraventas de inmuebles, uso residencial, por provincia", `https://opendata.registradores.org/dataset/dataset/compraventas-de-inmuebles-uso-residencial-por-provincia`
- Descarga directa (⚠️ **requiere UA de navegador**; sin él devuelve "Request Rejected" con HTTP 200):
  - CSV: `https://opendata.registradores.org/data-integration/compraventas-residencial-trimestres-provincias-es/RP_ComprvResid_2007-2t2026.csv` (✅ 577 KB, 5.617 líneas)
  - XLSX: `.../RP_ComprvResid_2007-2t2026.xlsx`
  - **El nombre del fichero cambia cada trimestre** (`2007-2t2026`). Hay que leer el enlace de la ficha del dataset o el `.jsonld` / `.xml` de metadatos (`https://opendata.registradores.org/dataset/dataset/3d2cc420-3aa4-482e-8114-834511aae1c7.jsonld`).
- Columnas: `ano;trim;geo;cod-ca;ca;cod-prv;prv;viv-num;viv-imp;viv-pm2;gar-num;gar-imp;gar-pm2;tras-num;tras-imp;tras-pm2`. Separador `;`, decimales con coma, con BOM UTF-8.
- **Contenido:** número de compraventas, importe medio y **€/m² registrados** de vivienda, **garaje y trastero** por provincia y trimestre. El €/m² de garaje y trastero sirve para validar el valor de los anejos.
- Licencia: **Open Data Commons ODbL 1.0**. Trimestral (última actualización 2026-08-24).
- La API CKAN estándar (`/api/3/action/...`) no responde: redirige a un reto JavaScript del WAF.
- **Prioridad: P0.**

### 5b. Estadística Registral Inmobiliaria (ERI)

- Página: `https://www.registradores.org/actualidad/portal-estadistico-registral/estadisticas-de-propiedad` (✅ 200).
- Formato: **solo PDF** (trimestral y anuario). Ejemplos: `https://www.registradores.org/documents/33383/148210/ERI_2025_2T.pdf/...` y `.../ERI+Anuario+2025.pdf/...`. Las URLs de Liferay llevan un UUID y una marca de tiempo, así que hay que obtenerlas de la página.
- Incluye el IPV de ventas repetidas (IPVVR), precio medio, superficie media, nacionalidad del comprador y periodo de tenencia.
- **Prioridad: P2.** El CSV de §5a cubre lo esencial y es más fácil de procesar.

### 5c. Nota simple informativa

- Se pide en la Sede: `https://sede.registradores.org/sede/sede-corpme-web/registro-de-la-propiedad/publicidad/nota-simple-informativa` (✅ 200; página SPA). Exige identificación, búsqueda por finca registral, IDUFIR/CRU, RC o titular, y pago con tarjeta.
- **Precio:** fuentes secundarias (Housfy, 2025) dan **9,02 € + IVA por finca** en la web del Colegio. El arancel registral de la nota simple es de unos 3 €; la diferencia corresponde al servicio telemático. **NO VERIFICADO en la Sede oficial.**
- **Contenido habitual** (no verificado con un ejemplo en esta sesión): datos registrales (Registro, tomo, libro, folio, nº de finca, IDUFIR/CRU), **descripción de la finca** (situación, superficie construida y/o útil, linderos, cuota de división horizontal, anejos vinculados), referencia catastral si consta, **titularidad** (titular, NIF, porcentaje y título de adquisición) y **cargas** (hipotecas con su responsabilidad, embargos, servidumbres, afecciones fiscales, limitaciones de VPO) y asientos pendientes.
- **Uso:** comprobar que la finca tasada es la registral (superficie registral frente a la catastral y la comprobada), cargas y VPO (que limitan el valor máximo legal). Los bancos ya suelen recibirla en el expediente hipotecario: **lo prioritario es extraerla del expediente**, más que pedirla.
- **Acceso para empresas o API:** el Colegio ofrece servicios a entidades (por ejemplo "Nota de localización de prestamistas", "Información continuada" y "Estadísticas a medida" en la Sede), pero **no se ha encontrado documentación pública de una API**. NO VERIFICADO. Hay que preguntar a CORPME (soporte.usuarios@corpme.es, 912 701 796).
- Hace falta **interés legítimo** (Ley Hipotecaria, arts. 221–222), y es dato personal sujeto al RGPD.
- **Prioridad: P1**, con datos aportados por el banco.

---

## 6. Banco de España

### 6a. Registro de sociedades de tasación homologadas

- Nuevo registro de entidades (renovado en septiembre de 2026): `https://app.bde.es/rbe_spa/home#/buscador` (✅ 200, app Angular).
  - Usa por debajo una API JSON **no documentada**, `https://app.bde.es/rbe_out/` (base leída de `https://app.bde.es/rbe_spa/assets/data/app.config.json`). `GET https://app.bde.es/rbe_out/ultima-actualizacion` → ✅ `{"fechaPublicacion":"2026-10-23"}`. El buscador es `GET /elementos?q=&sort=&lang=&page=`, pero la sintaxis de `q` no se ha averiguado (devolvió 403 y 500). También existen `/elementos/{id}`, `/elementos/{id}/pdf` y `/elementos/historia-completa/{id}`. **NO VERIFICADO** como vía de descarga estable.
  - Cuadro de mando (Power BI) con descarga: `https://www.bde.es/wbe/es/punto-informacion/contenidos/registros/registros-entidades/variaciones-995f02760e1ec91.html`.
- Índice de tipos de entidad (PDF de 1 página, de 2023): `https://www.bde.es/f/webbe/SGE/regis/Entidades_inscritas_en_los_Registros_Oficiales.pdf` (✅ 200). Incluye "Sociedades de tasación" como categoría y enlaza al buscador.
- Página del registro: `https://www.bde.es/wbe/es/punto-informacion/contenidos/registros/registros-entidades/` (✅ 200).
- **Recomendación MVP:** mantener una **tabla estática** de sociedades de tasación (nombre, código BdE de 4 dígitos, NIF, fecha de alta y baja), revisada a mano cada mes desde el buscador. Son unas pocas decenas de entidades; el número exacto no está verificado y las fuentes secundarias dan entre 18 y 28. Validar que el código y el nombre de la tasadora del informe existen y estaban de alta en la fecha de emisión. **Prioridad: P0** (tabla manual).
- Técnicos tasadores: **no existe un registro público de tasadores individuales**. Habría que validar la colegiación en cada colegio profesional, sin open data. NO VERIFICADO.

### 6b. Estadísticas de tasación del BdE

Boletín Estadístico, capítulo 9 (instituciones financieras no monetarias, sociedades de tasación). PDF (✅ 200; la ruta antigua `webbde/es/estadis/infoest/aXXXX.pdf` redirige con 301):

- `https://www.bde.es/webbe/es/estadisticas/compartido/datos/pdf/a0930.pdf`: número de tasaciones de inmuebles
- `.../a0935.pdf`: importe por clientela y finalidad
- `.../a0936.pdf`: número de tasaciones
- `.../a0937.pdf`: **distribución geográfica de las tasaciones de vivienda** (número e importe por tamaño de municipio; hasta 2024: 188.791 M€ y 781,6 mil tasaciones)
- `.../a0940.pdf`: tasaciones de vivienda por CCAA

Son datos agregados del sector, **sin desglose por sociedad**. El CSV equivalente no se ha localizado: las rutas `series/be09xx.csv` devuelven HTML. **Prioridad: P2.** La Asociación Española de Análisis de Valor (AEV) publica datos de actividad por asociados (NO VERIFICADO).

---

## 7. SNCZI: zonas inundables (MITECO)

**Qué verifica:** si el inmueble está en zona inundable T=10, 100 o 500 años, fluvial o marina. ECO/805 exige reflejarlo en el informe (condicionantes y advertencias).

- **WMS INSPIRE en IDEE** (✅ 200, recomendado): `https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones?service=WMS&request=GetCapabilities`
  - Capas: `NZ.Flood.FluvialT10`, `NZ.Flood.FluvialT100`, `NZ.Flood.FluvialT500`, `NZ.Flood.MarinaT100`, `NZ.Flood.MarinaT500`, todas *queryable*.
  - **GetFeatureInfo por punto** (✅ 200, `text/html`; también admite `application/vnd.ogc.gml` y `text/xml`):
    `https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&LAYERS=NZ.Flood.FluvialT100&QUERY_LAYERS=NZ.Flood.FluvialT100&CRS=EPSG:4326&BBOX={lat-d},{lon-d},{lat+d},{lon+d}&WIDTH=101&HEIGHT=101&I=50&J=50&INFO_FORMAT=application/vnd.ogc.gml`
- WFS INSPIRE en IDEE (`https://servicios.idee.es/wfs-inspire/riesgos-naturales/inundaciones`): ❌ timeout.
- WMS propios de MITECO (`https://wms.mapama.gob.es/sig/agua/ZI_LaminasQ100/wms.aspx` y equivalentes Q10, Q50, Q500): ❌ timeout desde este entorno (el DNS resuelve a 93.188.53.90). Siguen en los metadatos INSPIRE.
- **Shapefiles** (página ✅ 200: `https://www.miteco.gob.es/es/cartografia-y-sig/ide/descargas/agua/zi-lamina.html`). Cada enlace lleva a un formulario `https://gis.miteco.gob.es/descargas/app/DescargaFichero?f={fichero}` (✅ 200) que hace POST con token antiforgery ASP.NET. **Mi POST automatizado devolvió 400**, así que la descarga es **manual**.

| Fichero | Contenido | Tamaño (según la web) |
|---|---|---|
| `laminasPB-q10.zip` | ZI de alta probabilidad T=10 (Península y Baleares) | 834 MB |
| `laminas-q50.zip` | ZI frecuente T=50 | 504 MB |
| `laminasPB-q100.zip` | ZI T=100 (Península y Baleares) | 0,98 GB |
| `laminasCanarias-q100.zip` | ZI T=100 (Canarias) | 3,35 MB |
| `laminasPB-q500.zip` | ZI T=500 (Península y Baleares) | 9,72 MB (dato de la web; parece anómalo) |
| `laminasCanarias-q500.zip` | ZI T=500 (Canarias) | 3,33 MB |

- Formato SHP en ETRS89, escala 1:25.000.
- Licencia: uso libre citando «© Ministerio para la Transición Ecológica y el Reto Demográfico».
- **Prioridad: P0** vía WMS GetFeatureInfo por punto, sin descargar nada. P2 si se quiere cargar en PostGIS.

---

## 8. BOE: Portal de Subastas

- `https://subastas.boe.es/robots.txt` → `User-agent: * / Disallow: /` (✅ 200). **El rastreo automatizado del portal de subastas está vetado por robots.txt.**
- Estructura, comprobada con una sola consulta manual:
  - Búsqueda: `POST https://subastas.boe.es/subastas_ava.php`, con campos `accion=Buscar`, `campo[i]`/`dato[i]` (`SUBASTA.ESTADO.CODIGO`, `BIEN.TIPO` = `I` para inmuebles, `BIEN.COD_PROVINCIA`, `BIEN.CODPOSTAL`, `BIEN.LOCALIDAD`, `SUBASTA.FECHA_INICIO` y `SUBASTA.FECHA_FIN`...).
  - Detalle: `https://subastas.boe.es/detalleSubasta.php?idSub=SUB-JA-2026-265519&ver={1..5}`. Las pestañas son información general, autoridad gestora, bienes/lotes, relacionados y pujas (orden NO VERIFICADO). Los campos incluyen **Tasación**, Valor subasta, Cantidad reclamada, Puja mínima, Lotes y Anuncio BOE.
  - Enlace corto: `https://subastas.boe.es/ds.php?id={idSub}`.
- **Vía permitida: la API de datos abiertos del BOE**, cuya reutilización está autorizada por su aviso legal:
  - Sumario diario: `https://www.boe.es/datosabiertos/api/boe/sumario/{AAAAMMDD}` con `Accept: application/json` (✅ 200, ~400 KB). Las **subastas judiciales** van en la sección **IV** (solo con el id `SUB-JA-…`; el valor está en subastas.boe.es). Las **administrativas** (Seguridad Social, Hacienda, Defensa, puertos) van en la **V-B**, con el texto completo (ref. catastral, m²). *Corregido el 2026-10-24.*
  - Anuncio individual: `https://www.boe.es/diario_boe/xml.php?id=BOE-B-AAAA-NNNNN` (✅ 200). El texto contiene el `idSub` y el enlace `https://subastas.boe.es/ds.php?id=SUB-...`.
- **Uso:** como señal o testigo (precio de salida y tasación a efectos de subasta frente a la tasación hipotecaria), no como comparable de mercado. **Prioridad: P1** vía API del BOE. Consultar el detalle de subastas.boe.es solo de forma puntual y manual, o pedir autorización a la AEBOE.

---

## 9. Portales inmobiliarios y proveedores de datos con licencia

### robots.txt (✅ 200 en los cuatro)

| Portal | robots.txt | Condiciones de uso |
|---|---|---|
| Idealista | Permite `/` con muchas exclusiones (ordenaciones, `/ajax/*`, paginación `/*/pagina-*.htm`, fotos `/inmueble*/foto`) | **Prohíbe expresamente** acceder, monitorizar o copiar contenido *"utilizando para ello cualquier tipo de robot, spider, scraper u otro medio automático... sin nuestro permiso expreso y por escrito"*, así como *"infringir las restricciones de los avisos de exclusión de robots... así como puentear o burlar otras medidas"* (texto de los T&C publicados en PDF de 2020 y 2022). La página de condiciones vigente devuelve 403 a curl y WebFetch. |
| Fotocasa (Adevinta) | Bloquea bots concretos (HTTrack, WebCopier...); permite el resto con exclusiones | Aviso legal en `https://www.fotocasa.es/es/aviso-legal/ln` (✅ 200): contenidos, **estructura, selección y ordenación** protegidos por propiedad intelectual (derecho *sui generis* de bases de datos). No se ha encontrado una cláusula literal anti-robots. |
| Habitaclia (Adevinta) | Prohíbe parámetros de filtro, paginación (`pag=`) y coordenadas (`geo=`, `hMinLat=`) | Aviso legal `https://www.habitaclia.com/hab_cliente/legal_aviso.asp` (✅ 200): *"Todos los contenidos, incluyendo... bases de datos... están sujetos a derechos de propiedad industrial e intelectual... sin la previa y expresa autorización"*. |
| pisos.com | Prohíbe `/busqueda/$`, `*.aspx`, `/WS/` y `/mapa/`; bloquea HTTrack, WebCopier... | Aviso legal `https://www.pisos.com/avisolegal` (✅ 200): el acceso no otorga derecho de *"explotación, reproducción, distribución"*. |

**Conclusión legal-práctica:** el scraping sistemático de portales para alimentar un producto comercial choca con los T&C (Idealista de forma explícita) y con el derecho *sui generis* sobre bases de datos (Ley de Propiedad Intelectual, art. 133). Para un cliente bancario el riesgo reputacional es alto. **Recomendación: licenciar** (idealista/data, Brainsre...) o limitarse a la consulta manual de los testigos que aporte la propia tasación.

### Idealista Search API (oficial)

- Solicitud: `https://developers.idealista.com/access-request` (✅ 200). Es un formulario: *"Search API lets you integrate property information published on idealista into your site or app. To receive an API key get in touch and tell us a bit about your project."*
- Token OAuth: `https://api.idealista.com/oauth/token` (✅ responde 401 sin credenciales; el endpoint existe).
- Cuotas, campos y si permite uso analítico o almacenamiento: **NO VERIFICADO**. Hay cifras de terceros (100 peticiones al mes, 50 resultados por página) sin fuente oficial. Pensada para mostrar anuncios, no para extraer datos masivamente.

### idealista/data (comercial)

- `https://www.idealista.com/data/` (✅ 200). Segmentos: "Bancos y Servicers" y "**Tasadoras**". Ofrece APIs y big data, datos históricos desde 2005, ~2,6 M inmuebles por trimestre y 15.584 zonas (hasta sección censal), valoración y auditoría de carteras. **Precio no público** (formulario "Pedir más información").

### Otros proveedores

| Proveedor | Qué vende (según su web o fuentes) | Precio |
|---|---|---|
| **Brainsre** (`https://www.brainsre.com/`, ✅ 200) | Plataforma de big data inmobiliario: oferta actual e histórica de **todos los portales**, **transacciones del registro**, valoración con testigos, histórico de precios, exportación a Excel, envío de datos a medida (testigos, licencias de obra nueva) | No público |
| **Tinsa Digital** (`https://www.tinsadigital.com/que-hacemos/avm/`, ✅ 200) | AVM por fichero o API, con indicadores de fiabilidad CL y FSD; dice estar homologada por la European AVM Alliance y alineada con la Circular 4/2017 del BdE. Valoración masiva de carteras | No público |
| **Gesvalt** (`https://www.gesvalt.es/`, ✅ 200) | Valoración masiva/AVM vía API, CSV, SaaS o iframe para entidades financieras. Tasación oficial al público "desde 165 €" | AVM no público |
| **Sociedad de Tasación** (`https://www.st-tasacion.es/`, ✅ 200, SPA) | Productos de datos y AVM: NO VERIFICADO | NO VERIFICADO |
| **Atlas Real Estate Analytics** | Consultora madrileña de data science inmobiliario (2019–2020, ~6 empleados según directorios; herramienta "Fragua"). `atlasrea.com` es **otra empresa** (EE. UU.). Web oficial no localizada | NO VERIFICADO |

Advertencia de conflicto de interés: Tinsa, Gesvalt y ST son a la vez **sociedades de tasación** cuyos informes se van a auditar. Usar su AVM para validar sus propias tasaciones (o las de sus competidoras) requiere cautela metodológica y contractual. **Prioridad: P2** (presupuesto de 10–50 k€/año: pedir ofertas a idealista/data y Brainsre).

---

## 10. Certificados de eficiencia energética (registros autonómicos abiertos)

**Qué verifica:** calificación energética (letra de consumo y emisiones), año de construcción, superficie, tipo de edificio y **referencia catastral**, que permite cruzarlos con la tasación. ECO/805 y la normativa de transparencia exigen reflejar el certificado.

| CCAA | URL de descarga | Formato | Tamaño | Licencia | Estado |
|---|---|---|---|---|---|
| **Comunidad de Madrid** | Ficha: `https://datos.comunidad.madrid/dataset/registro_certificados_eficiencia_energetica`. API: `https://datos.comunidad.madrid/api/3/action/package_show?id=registro_certificados_eficiencia_energetica`. Ficheros: `.../download/registro_ceee_anterior_a_2024.zip` (137 MB), `..._2024.zip` (20 MB), `..._2025.zip` (18 MB), `registro_certificados_eficiencia_energetica_2026.csv` (86 MB) | CSV `;` UTF-8 (columnas `edif_refcat`, `edif_año`, `edif_superf`, `edif_tipo`, calificaciones...) | ~260 MB | CC-BY | ✅ 200 (actualizado 2026-10-05) |
| **Cataluña (ICAEN)** | Socrata `j6ii-t3w2`: `https://analisi.transparenciacatalunya.cat/resource/j6ii-t3w2.json?$limit=50000&$offset=N` (SoQL). Metadatos: `https://analisi.transparenciacatalunya.cat/api/views/j6ii-t3w2.json` | JSON/CSV (`referencia_cadastral`, `metres_cadastre`, `qualificaci_de_consum_d`...) | **1.343.261 filas** | Licencia de datos abiertos de la Generalitat | ✅ 200 (actualizado 2026-10-05). El endpoint `rows.csv` devolvió `Content-Length: 0` y una cabecera de *deprecation/sunset* de Socrata: usar `/resource/` paginado |
| **Comunitat Valenciana (IVACE)** | `https://dadesobertes.gva.es/dataset/med-eficiencia-energetica-edificis-ivace` → CSV por provincia: `.../certificacion-energetica-de-edificios-en-alicante.csv` (72 MB), `...-castellon.csv` (20 MB), `...-valencia.csv` (65 MB) | CSV `;`, Latin-1 (`REFERENCIA_CATASTRAL`, `ANYO_CONSTRUCCION`, letras) | ~157 MB | CC-BY | ✅ 200 (actualizado 2026-10-20) |
| **Canarias** | `https://datos.canarias.es/catalogos/general/dataset/ca2b3a6c-241b-4fe1-ba6b-f35257ce9604/resource/7094974b-2642-45bf-a5c7-636692d2b3ec/download/rcee.csv` | CSV `;` con comillas (`referencia_catastral`...) | 139 MB | Aviso legal del Gobierno de Canarias | ✅ 200 |
| **Aragón** | `https://opendata.aragon.es/datos/catalogo/dataset/registro-de-certificacion-de-eficiencia-energetica-de-edificios-de-aragon` (CSV/JSON/XML/XLSX por provincia, con RC y coordenadas, CC-BY 4.0 según la búsqueda) | — | — | CC-BY 4.0 | ❌ timeout. **NO VERIFICADO** |
| Andalucía, Castilla y León, Euskadi, resto | No encontrados en esta sesión | — | — | — | **NO VERIFICADO** |

Las URLs completas de Madrid, C. Valenciana y Canarias contienen UUID de recurso CKAN. Lo más robusto es resolverlas en cada ejecución con `package_show`. **Prioridad: P1** (Madrid como P0 si el piloto es en Madrid).

---

## 11. Otras fuentes gratuitas útiles

### 11a. CartoCiudad (CNIG/IGN): geocodificación

- Geocodificación directa: `https://www.cartociudad.es/geocoder/api/geocoder/find?q={dirección}` (✅ 200 JSON). También `findJsonp`.
- Candidatos: `https://www.cartociudad.es/geocoder/api/geocoder/candidates?q={texto}&limit=N` (✅ 200)
- Inversa: `https://www.cartociudad.es/geocoder/api/geocoder/reverseGeocode?lon={lon}&lat={lat}` (✅ 200)
- Devuelve municipio (código INE), CP, lat/lon, tipo de vía y número, y **`refCatastral` de la parcela (14 caracteres)**. Por ejemplo, "calle alcala 100, madrid" → `2853604VK4725D`, que coincide con el resultado de Catastro.
- Gratis, sin clave. Sirve para normalizar la dirección del informe y enlazarla con Catastro. **Prioridad: P0.**

### 11b. Ayuntamiento de Madrid (datos.madrid.es, CKAN)

- Catálogo de edificios protegidos: `https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/PLANEAMIENTO/ACTUALIZADO/CATALOGOS/CATALOGO_EDIFICIOS_PROTEGIDOS_CSV.zip` (y `CATALOGO_EDIFICIOS_PROTEGIDOS.zip` con geometría), con licencia CC-BY 4.0. Verifica el grado de protección, que condiciona el valor y las obras.
- Licencias urbanísticas otorgadas: `https://datos.madrid.es/dataset/640505-0-licencias-urbanisticas-otorgadas/resource/640505-1-licencias-urbanisticas-otorgadas/download/licencias.csv` (2,9 MB) y `.xlsx`. Verifican reformas u obra nueva declaradas en la tasación.
- Búsqueda: `https://datos.madrid.es/api/3/action/package_search?q=...` (✅ 200).
- **ITE/IEE:** **no hay dataset abierto** en datos.madrid.es (búsquedas "ITE", "IEE" y "inspeccion tecnica" sin resultados relevantes). Existe una consulta web individual en el Registro de Edificios del Ayuntamiento (NO VERIFICADO el endpoint). El registro autonómico de IEE (Decreto 103/2016) tampoco es open data.
- **Prioridad: P1.**

### 11c. INE: Atlas de Distribución de Renta de los Hogares (ADRH)

- Tablas: `https://servicios.ine.es/wstempus/js/ES/TABLAS_OPERACION/ADRH` (✅ 200, 540 tablas: "Indicadores de renta media y mediana", una por provincia, con IDs como 30656, 30824, 30833...). Datos con `DATOS_TABLA/{id}`.
- Granularidad: municipio, distrito y **sección censal**. Anual. Es una variable de calidad de la ubicación para el AVM y para la coherencia del entorno descrito.
- **Prioridad: P1.**

### 11d. IGN/CNIG

- PNOA máxima actualidad WMS: `https://www.ign.es/wms-inspire/pnoa-ma?service=WMS&request=GetCapabilities` (✅ 200). Sirve para revisar entorno y fotos.
- Centro de descargas: `https://centrodedescargas.cnig.es/CentroDescargas/` (✅ 200): MDT, LiDAR, ortofotos, BTN.
- **Prioridad: P2.**

### 11e. Otras ideas (NO VERIFICADO)

- Precios medios de mercado o valores de comprobación del ITP que publican algunas CCAA.
- Estadística de Hipotecas del INE (`HPT`): contexto del LTV medio.
- Datos del Catastro sobre *"estadísticas catastrales"* e IBI (enlazadas desde la Sede de descargas).

---

## Pendientes y riesgos identificados

1. **Notariado y portales:** sus condiciones prohíben el uso comercial o el scraping. Hay que decidir entre licenciar y prescindir. Las alternativas libres (MIVAU, Registradores, Catastro) cubren el benchmarking municipal y provincial, pero **no dan testigos individuales**.
2. **Testigos individuales libres:** ninguna fuente pública da precios de transacción por inmueble. La única "muestra" individual gratuita son las subastas del BOE (sesgadas a la baja) y los propios testigos que declara la tasación.
3. **Valor de referencia:** solo consulta individual identificada; no escala.
4. **SNCZI:** la descarga de shapefiles no es scriptable (formulario antiforgery). El WMS de IDEE basta para el MVP.
5. **Catastro OVC:** riesgo de bloqueo por IP durante 10 días si se abusa. Aplicar caché y limitación de ritmo.
6. **País Vasco y Navarra:** usan catastros forales con servicios distintos (feeds ATOM enlazados en el feed de la DGC, con estructura propia y no analizada).
