# Hoja de ruta y bitácora

> Cada sesión (desde el PC o el celular) empieza leyendo este archivo y termina actualizándolo.
> Para retomar, basta decirle al agente: **"continúa con compras-publicas-cl"**.

## Siguiente tarea
1. **Revisar `data/logs/detalle_corridas.jsonl`** después de la corrida nocturna: si `requests_por_licitacion` sigue cerca de 1,5, ver qué códigos HTTP dominan en `respuestas_http` y ajustar la pausa base (`--pausa`).
2. **P1.5 — marts dbt:** `fct_licitaciones` (detalle + resultado + monto adjudicado), `dim_organismos`, `dim_rubros`, `fct_ofertas_adjudicadas` (proveedor × ítem). Conviene esperar unas noches más de backfill para tener más meses.

## Proyecto 1 · Pipeline + modelo en producción (~2 semanas)
- [x] P1.1 Estructura del repo, cliente de la API, ingesta incremental, tests, CI
- [x] P1.2 Ticket como secret de GitHub + backfill de listados diarios (2026-04-01 → 2026-10-13) vía GitHub Actions
- [x] P1.3 Descarga de detalle por licitación (con caché, checkpoint, tope de 9.000 requests/noche y madurez de 60 días) — backfill en curso vía `detalle.yml`
- [x] P1.4 Carga a DuckDB + modelos dbt `staging`: `stg_listados`, `stg_detalle`, `stg_detalle_items` (16 tests dbt)
- [ ] P1.5 Marts dbt: licitaciones, organismos, rubros, oferentes
- [ ] P1.6 EDA en notebook + definición del objetivo (¿licitación desierta? ¿n° de oferentes?)
- [ ] P1.7 Baseline + LightGBM con MLflow (split temporal, varias métricas)
- [ ] P1.8 API de predicción con FastAPI + Docker
- [ ] P1.9 Monitoreo de drift con Evidently + job programado diario
- [ ] P1.10 Demo pública desplegada + README con resultados

## Proyecto 2 · Estudio causal (~1 semana)
- [ ] P2.1 Identificar un cambio normativo/umbral con fecha clara
- [ ] P2.2 Diseño (DiD o regresión discontinua) + supuestos
- [ ] P2.3 Estimación, robustez y memo de negocio de 1 página

## Proyecto 3 · Agente RAG + Text-to-SQL (~2 semanas)
- [ ] P3.1 Corpus normativo (Ley 19.886 y reglamento) + RAG híbrido con reranking
- [ ] P3.2 Text-to-SQL sobre el warehouse con guardrails (solo SELECT, límites)
- [ ] P3.3 Set de evaluación de 50–100 preguntas + métricas (exactitud, fidelidad, costo, latencia)
- [ ] P3.4 Interfaz demo + README con resultados de evaluación

## Bitácora
- **2026-10-14** — Creado el repo: estructura, `AGENTS.md`, `DECISIONS.md`, cliente de la API con reintentos, ingesta incremental por día (no repite descargas), 2 tests pasando, CI en GitHub Actions.
- **2026-10-14** — Ticket configurado. Remoto `origin` → github.com/CarlosIgRuz/compras-publicas-cl (integrado su commit inicial). Corregida fuga del ticket en mensajes de error (+test). Añadido `descargar.bat` para ingesta nativa en Windows. Hallazgo: el proxy del agente bloquea la API de ChileCompra.
- **2026-10-14** — Repo publicado en GitHub. Ingesta movida a GitHub Actions (`ingesta.yml`): cron nocturno 03:15 Chile + ejecución manual con fechas; ticket como secret cifrado. Prueba 2026-10-01: 910 licitaciones, 35 KB comprimido. Lanzado backfill de 6 meses.
- **2026-10-14** — Revisados los 12 días vacíos del backfill: todos son domingos (los otros domingos traen 0–5 licitaciones), no fallas de la API → no se re-descargan. P1.3: `compras.ingest.detalle` + workflow nocturno `detalle.yml`. Descarga el detalle por código de días publicados hace ≥60 días, sin repetir códigos (472 aparecen en dos días), con checkpoint `.parcial.jsonl` para retomar si se corta, tope de 9.000 requests y 240 min, y tope de 100 fuera de 22–07 Chile. 6 tests nuevos (9 en total).
- **2026-10-14** — P1.4 (primera mitad): proyecto dbt-duckdb (`dbt/`) que lee `data/raw` directo y materializa en `data/warehouse.duckdb`. `stg_listados` con tipos, estado legible, tipo de licitación desde el código y deduplicación (266 licitaciones venían repetidas en el mismo día con milisegundos distintos; lo detectó el test de unicidad). Test pytest que corre `dbt build` sobre datos de juguete; CI instala dbt. **Hallazgo:** el listado diario no es "publicadas ese día", sino el día del último evento según el estado actual (adjudicadas: día de adjudicación; desiertas/cerradas: día de cierre; publicadas: día de publicación). Las fechas de publicación reales vendrán del detalle.
- **2026-10-14** — Primera noche de detalle: terminó sin errores, con 5.811 licitaciones (22 días completos y un checkpoint del 22-abr) y 4,9 MB (~0,85 KB por licitación; el backfill completo pesaría ~60 MB). Se cortó por el tope de 9.000 requests y no por tiempo: ~1,55 requests por licitación. Los intervalos entre descargas (bimodales en 1 y 2 s) sugieren que la API rechaza cerca de la mitad de los primeros intentos. Agregado: conteo de respuestas por código HTTP, pausa adaptativa (base 1 s, se alarga ante rechazos) y bitácora `data/logs/detalle_corridas.jsonl` por corrida, porque los logs de Actions no son accesibles desde el agente. P1.4 completa: `stg_detalle` (sin datos personales de funcionarios) y `stg_detalle_items` (una fila por línea; un ítem puede adjudicarse a varios proveedores). Estados 15 y 16 confirmados como revocada y suspendida.
