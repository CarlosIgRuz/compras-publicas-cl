# Hoja de ruta y bitácora

> Cada sesión (desde el PC o el celular) empieza leyendo este archivo y termina actualizándolo.
> Para retomar, basta decirle al agente: **"continúa con compras-publicas-cl"**.

## Siguiente tarea
**P1.2 — Primera descarga real.** Ticket ya en `.env`. La red del agente bloquea `api.mercadopublico.cl`: la ingesta se ejecuta en Windows con `descargar.bat` (o se pide habilitar el dominio en la configuración de red de Claude). Push a GitHub lo hace el usuario desde Windows (`git push -u origin main`).

## Proyecto 1 · Pipeline + modelo en producción (~2 semanas)
- [x] P1.1 Estructura del repo, cliente de la API, ingesta incremental, tests, CI
- [ ] P1.2 Ticket en `.env` + backfill de ~6 meses de listados diarios
- [ ] P1.3 Descarga de detalle por licitación (con caché, respetando cupo de 10k/día)
- [ ] P1.4 Carga a DuckDB + modelos dbt `staging` (limpieza, tipos, fechas)
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
