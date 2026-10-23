# tasacion-ia

Sistema para validar tasaciones inmobiliarias (ECO/805, residencial, España): ingiere el PDF de la tasación en un esquema estructurado, la contrasta con fuentes externas y emite un veredicto **validada / con dudas / revisión obligatoria** con sub-scores explicables.

## Arranque rápido

```bash
docker compose up -d   # PostGIS en localhost:5433 con el esquema aplicado
uv sync
```

Todas las vías de instalación (Docker, Postgres nativo, gestionado, pip, GDAL) y la estimación de disco: [`docs/instalacion.md`](docs/instalacion.md).

## Decisiones tomadas

- **Cliente objetivo**: banco / prestamista hipotecario que recibe tasaciones de terceros.
- **Score**: compuesto con sub-scores visibles (valor, calidad/cumplimiento, fraude). MVP: desviación de valor + coherencia interna.
- **Ámbito**: España, tasaciones ECO/805, solo residencial.
- **Entrada**: PDFs nativos y escaneados, de varias sociedades de tasación.
- **Ground truth**: no hay al inicio → v1 no supervisada (AVM + reglas); recoger etiquetas desde el día 1.
- **Presupuesto datos de pago**: 10–50 k€/año.
- **Ingesta**: pipeline propio (parsing/OCR → extracción LLM con salida estructurada → validación → BD), estilo anyformat.
- **Horizonte**: MVP en 4–6 semanas, 1–2 personas. Stack: Python, Postgres + PostGIS.
- **Datos**: scraping cuando sea posible, además de fuentes públicas.

## Pendiente de decidir

Ver ronda 2 del diseño: semáforo y reglas bloqueantes, alcance legal del scraping, profundidad del esquema, verificación de testigos, metodología AVM, fuentes de pago, calibración con tasador senior, PII/RGPD, UI de revisión.
