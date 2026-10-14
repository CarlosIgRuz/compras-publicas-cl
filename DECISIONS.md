# Registro de decisiones

Formato: fecha · decisión · alternativas consideradas · por qué · (corrección al agente, si hubo)

- **2026-10-14 · Dominio: compras públicas de Chile (Mercado Público).** Alternativas: CMF, INE, DTPM. Por qué: API oficial gratuita, datos reales y desordenados, relevancia local, y permite los tres proyectos (ML, causal, LLM) sobre un mismo warehouse.
- **2026-10-14 · Warehouse local en DuckDB + dbt.** Alternativas: Postgres, Snowflake. Por qué: cero servidor, lee Parquet directo, dbt-duckdb permite mostrar habilidades de analytics engineering sin costo.
- **2026-10-14 · Cumplimiento de condiciones de uso de la API.** Descargas masivas (backfill) solo en horario nocturno 22:00–07:00, tope interno bajo el límite de 10k/día, y atribución "Fuente: Dirección ChileCompra" en todo lo publicado.
- **2026-10-14 · Ingesta en GitHub Actions, no en el PC ni en el agente.** Alternativas: script en Windows (requiere PC encendido), red del agente (bloquea la API). Por qué: corre sin depender de un equipo, el ticket queda cifrado como secret, y demuestra un pipeline programado real. Datos crudos en `data/raw` como `.json.gz` (~35 KB/día).
