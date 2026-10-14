# Compras Públicas CL — de la API al agente

Ecosistema de datos end-to-end sobre las compras públicas de Chile (API de Mercado Público / ChileCompra).
Construido con agentes de IA bajo mi dirección: las decisiones, validaciones y evaluaciones son mías (ver `DECISIONS.md`).

| # | Proyecto | Perfil que demuestra | Estado |
|---|----------|----------------------|--------|
| 1 | Pipeline diario + modelo en producción (API → DuckDB → dbt → MLflow → FastAPI → monitoreo de drift) | ML Engineer / Data Engineer | 🚧 en curso |
| 2 | Estudio causal sobre competencia en licitaciones | Data Scientist (experimentación / causalidad) | ⏳ |
| 3 | Agente RAG + Text-to-SQL con set de evaluación propio | AI Engineer | ⏳ |

## Arquitectura (objetivo)
```
API Mercado Público ──► ingest (Python) ──► data/raw (JSON/Parquet)
                                   │
                                   ▼
                     DuckDB warehouse ◄── dbt (staging → marts)
                          │        │
              modelo ML ◄─┘        └─► agente Text-to-SQL + RAG normativa
           (MLflow, FastAPI)
                 │
         monitoreo drift (Evidently)
```

## Uso rápido
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # pega tu ticket de la API
python -m compras.ingest.extract --desde 2026-09-01 --hasta 2026-09-07
```

## Estructura
- `src/compras/ingest` — cliente de la API e ingesta incremental
- `dbt/` — transformaciones SQL (staging, marts)
- `src/compras/models` — entrenamiento y servicio del modelo
- `docs/ROADMAP.md` — plan y bitácora de avance
- `AGENTS.md` — instrucciones que guían a los agentes en este repo
- `DECISIONS.md` — decisiones técnicas tomadas por mí y correcciones al agente

## Fuente de los datos
Datos obtenidos de la API de Mercado Público. **Fuente: Dirección ChileCompra.**
El uso se rige por las [Políticas y Condiciones de Uso de la API](https://api.mercadopublico.cl): máximo 10.000 solicitudes diarias por ticket; las descargas masivas se programan entre 22:00 y 07:00.
