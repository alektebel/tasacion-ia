"""Esquema de extracción de un informe de tasación ECO/805/2003 (con la reforma ECM/599/2025).

Refleja las tablas tasacion.tasacion / finca / testigo / testigo_coeficiente. Los nombres de
campo coinciden con las columnas para que la carga sea directa. Todo campo es opcional:
si el informe no lo trae, el extractor devuelve null en vez de inventarlo.

No se extraen datos personales (solicitante, titulares, NIF): no los necesita el scoring.
"""

from typing import Literal

from pydantic import BaseModel, Field

Confianza = Literal["alta", "media", "baja"]


class Coeficiente(BaseModel):
    factor: str = Field(description="superficie, ubicacion, antiguedad, estado, planta, calidad, negociacion u otro")
    valor: float = Field(description="Coeficiente multiplicativo, p.ej. 0.95 o 1.05")


class Testigo(BaseModel):
    orden: int
    tipo_dato: Literal["oferta", "transaccion", "tasacion"] | None
    fuente: str | None = Field(description="Portal, inmobiliaria o registro de donde sale el testigo")
    url: str | None
    ref_anuncio: str | None
    telefono_contacto: str | None
    fecha_dato: str | None = Field(description="AAAA-MM-DD")
    direccion: str | None
    codigo_postal: str | None
    ref_catastral: str | None
    planta: str | None
    sup_construida: float | None = Field(description="m²")
    sup_util: float | None = Field(description="m²")
    dormitorios: int | None
    banos: int | None
    anio_construccion: int | None
    estado_conservacion: str | None
    precio: float | None = Field(description="€ totales del testigo")
    precio_unitario: float | None = Field(description="€/m² antes de homogeneizar")
    coef_homogeneizacion: float | None = Field(description="Coeficiente total aplicado")
    precio_homogeneizado: float | None = Field(description="€/m² tras homogeneizar")
    peso: float | None = Field(description="Ponderación del testigo, 0-1")
    coeficientes: list[Coeficiente] = Field(description="Desglose por factor, si el informe lo da")


class Finca(BaseModel):
    orden: int
    tipo: Literal["vivienda", "garaje", "trastero", "local", "otro"]
    es_principal: bool
    ref_catastral: str | None = Field(description="20 caracteres")
    finca_registral: str | None
    registro_propiedad: str | None
    tomo: str | None
    libro: str | None
    folio: str | None
    idufir: str | None = Field(description="IDUFIR / CRU")
    direccion: str | None = Field(description="Dirección completa tal como aparece")
    tipo_via: str | None
    nombre_via: str | None
    numero: str | None
    escalera: str | None
    planta: str | None
    puerta: str | None
    codigo_postal: str | None
    municipio: str | None
    provincia: str | None
    lat: float | None = Field(description="Sólo si el informe da coordenadas")
    lon: float | None
    sup_util_comprobada: float | None
    sup_construida_comprobada: float | None
    sup_construida_con_comunes: float | None
    sup_util_registral: float | None
    sup_construida_registral: float | None
    sup_catastral: float | None
    sup_adoptada: float | None = Field(description="Superficie que el informe usa para valorar")
    sup_parcela: float | None
    anio_construccion: int | None
    anio_rehabilitacion: int | None
    dormitorios: int | None
    banos: int | None
    ascensor: bool | None
    exterior: bool | None
    orientacion: str | None
    estado_conservacion: str | None
    calidad_constructiva: str | None
    certificado_energetico: Literal["A", "B", "C", "D", "E", "F", "G"] | None
    ocupacion: str | None
    proteccion_publica: bool | None = Field(description="VPO u otro régimen de protección")
    valor_unitario: float | None = Field(description="€/m² adoptado")
    valor_finca: float | None = Field(description="€")
    testigos: list[Testigo]


class Evidencia(BaseModel):
    ruta: str = Field(description="Campo al que se refiere, p.ej. valor_tasacion o fincas/0/sup_adoptada")
    pagina: int | None = Field(description="Página del PDF (1 = primera)")
    texto: str = Field(description="Fragmento literal del informe que respalda el valor")
    confianza: Confianza


class Aviso(BaseModel):
    tipo: Literal["contradiccion", "laguna", "nota_lectura"] = Field(
        description="contradiccion: el informe se contradice a sí mismo o con sus anexos (nota simple, "
        "catastro...); laguna: falta algo que la ECO/805 exige o que el valor necesita; "
        "nota_lectura: decisión o duda del extractor al leer (ilegible, campo ambiguo...)"
    )
    gravedad: Literal["alta", "media", "baja"] = Field(
        description="alta si puede cambiar el valor o la validez de la tasación (cargas omitidas, "
        "superficies incompatibles, testigos dudosos); baja si es formal"
    )
    texto: str
    paginas: list[int]


class TasacionExtraida(BaseModel):
    sociedad_nombre: str | None
    sociedad_codigo_bde: str | None = Field(description="Nº de inscripción en el registro del Banco de España")
    sociedad_cif: str | None
    tecnico_nombre: str | None
    tecnico_num_colegiado: str | None
    tecnico_colegio: str | None
    tecnico_titulacion: str | None
    num_informe: str | None
    finalidad: str | None = Field(description="p.ej. garantia_hipotecaria")
    fecha_visita: str | None = Field(description="AAAA-MM-DD")
    fecha_emision: str | None = Field(description="AAAA-MM-DD")
    fecha_caducidad: str | None = Field(description="AAAA-MM-DD")
    metodo_principal: Literal[
        "comparacion", "coste", "actualizacion_rentas", "residual_estatico", "residual_dinamico"
    ] | None
    valor_tasacion: float | None = Field(description="Valor final a efectos hipotecarios, €")
    valor_mercado: float | None
    valor_hipotecario: float | None = Field(description="Valor hipotecario o sostenible")
    valor_reposicion_bruto: float | None
    valor_reposicion_neto: float | None
    valor_seguro: float | None
    condicionantes: list[str]
    advertencias: list[str]
    fincas: list[Finca]
    evidencias: list[Evidencia] = Field(
        description="Una por cada valor, superficie, ref. catastral, fecha y testigo extraído"
    )
    avisos_extraccion: list[Aviso]
