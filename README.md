# Chilean Public Procurement — from the API to the agent

[![CI](https://github.com/CarlosIgRuz/compras-publicas-cl/actions/workflows/ci.yml/badge.svg)](https://github.com/CarlosIgRuz/compras-publicas-cl/actions/workflows/ci.yml)

End-to-end data ecosystem on Chile's public procurement, built on the official Mercado Público (ChileCompra) API.
Built with AI coding agents under my direction: the decisions, validations and evaluations are mine — see [`DECISIONS.md`](DECISIONS.md) for every decision, the alternatives considered and the corrections made along the way.

> 🇨🇱 **Resumen en español** al final.

| # | Project | Skills it demonstrates | Status |
|---|---------|------------------------|--------|
| 1 | Daily pipeline + model in production (API → DuckDB → dbt → MLflow → FastAPI → drift monitoring) | ML / Data Engineering | 🚧 in progress |
| 2 | Causal study on competition in public tenders | Data Science (causal inference) | ⏳ |
| 3 | RAG + Text-to-SQL agent with its own evaluation set | AI Engineering | ⏳ |

## The question
**Will this public tender end up void ("desierta")?** — predicted at the moment it is published, so the buyer can still adjust deadlines or terms.
About **1 in 5** tenders with an outcome ends void, a remarkably stable rate month to month; it ranges from 3% to 46% across procedure types and from 8% to 27% across product categories. Only ~31% of void tenders received no bids at all: the rest got bids that were rejected.

![Monthly composition and % void](docs/img/eda_meses.png)
![% void by procedure type](docs/img/eda_tipos.png)

## Results
Temporal split by publication date (train Apr 1 → Jun 1, validation → Jun 11, test Jun 11 → Jun 23, 2026; 21,856 tenders with an outcome). Every feature is known at publication time, and the buyer's history is computed point-in-time (only outcomes resolved *before* publication, enforced by a test). Full report: [`reports/modelo_resultados.md`](reports/modelo_resultados.md).

| Model (test set, 20.5% void) | PR-AUC [95% CI] | ROC-AUC | Brier | % void among the 10% highest-risk |
|---|---|---|---|---|
| Baseline: global rate | 0.205 | 0.500 | 0.163 | 20.5% |
| Baseline: historical rate by type × category | 0.264 [0.24–0.29] | 0.589 | 0.160 | 29.9% |
| Logistic regression | 0.317 [0.29–0.35] | 0.634 | 0.156 | 37.8% |
| **LightGBM** | **0.316 [0.29–0.35]** | **0.640** | **0.155** | **39.6%** |

**Reading:** flagging the riskiest 10% of new tenders finds void ones at ~2× the base rate, and both models beat a strong rule-based baseline. The signal is real but moderate — whether a tender ends void also depends on bids and evaluation that happen *after* publication. Top drivers: product category, number of line items, the buyer's past void rate and the estimated amount.

**Calibration:** early stopping uses log-loss, so predicted probabilities match observed rates (e.g. 0.34 predicted → 0.32 observed in the top quintile) — important because the API shows the probability to users.

**Leakage checks:** with shuffled labels both models drop to ROC-AUC ≈ 0.50. The planned closing date was removed as a feature: it comes from the final record (deadline extensions happen after publication) and added only +0.01 PR-AUC, within the confidence interval.

## Prediction API
FastAPI service that scores a tender at publication time and explains the top three drivers (LightGBM SHAP contributions). The buyer's history is looked up from artifacts exported at training time, and a test guarantees the API builds features exactly like the training pipeline (no training/serving skew). The Docker image is built and smoke-tested on every change by [a GitHub Actions workflow](.github/workflows/docker.yml).

```bash
docker build -t compras-api . && docker run -p 8000:8000 compras-api   # docs at http://localhost:8000/docs
curl -X POST localhost:8000/predecir -H 'Content-Type: application/json' \
  -d '{"tipo":"LE","rubro_principal":"Servicios de construcción y mantenimiento","n_items":6,"monto_estimado_clp":40000000}'
```
```json
{"probabilidad_desierta": 0.29, "nivel": "medio", "tasa_base": 0.205,
 "factores": [{"variable": "rubro", "efecto": "sube el riesgo", "contribucion": 0.21}, "..."],
 "fuente": "Dirección ChileCompra"}
```

## Engineering highlights
- **Nightly ingestion on GitHub Actions** that respects the API terms: a self-imposed daily quota of 9,000 requests tracked in a versioned run log, downloads only between 22:00 and 07:00 Chile time, adaptive back-off (~1.01 requests per tender), checkpoints and per-tender retries so one API error never stops a night. Because GitHub cron triggers proved unreliable (often hours late or dropped), a scheduled external dispatcher is the primary trigger and cron is the fallback.
- **dbt + DuckDB warehouse** read straight from the raw JSON: staging, marts and a point-in-time ML table, with 34 data tests.
- **Selection-bias fix:** daily listings show each tender on the date of its *last* event, so naive cohorts over-represent quickly resolved (void) tenders. The model uses a cohort with complete outcome observability — documented in [`DECISIONS.md`](DECISIONS.md).
- **Privacy by design:** public servants' names, emails and phone numbers are dropped in staging.

## Architecture
```
Mercado Público API ──► ingest (Python, GitHub Actions) ──► data/raw (JSON, versioned)
                                    │
                                    ▼
                      DuckDB warehouse ◄── dbt (staging → marts → ml)
                           │        │
          ML model (MLflow) ◄┘        └─► Text-to-SQL + RAG agent  (project 3)
                 │
      FastAPI + Docker (prediction API) ──► drift monitoring (next)
```

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # add your API ticket
python -m compras.ingest.extract --desde 2026-09-01 --hasta 2026-09-07
dbt build --project-dir dbt --profiles-dir dbt       # builds data/warehouse.duckdb from data/raw
PYTHONPATH=src python -m compras.models.train        # trains, writes reports/ and artifacts/modelo
uvicorn compras.api.app:app --app-dir src            # prediction API at http://localhost:8000/docs
```

## Repository layout
- `src/compras/ingest` — API client, daily listings and nightly detail download
- `dbt/` — SQL transformations (staging, marts, ml)
- `src/compras/models` — training, evaluation and export of the serving model
- `src/compras/api` — FastAPI prediction service (`Dockerfile`, `artifacts/modelo`)
- `notebooks/` — exploratory analysis
- `docs/ROADMAP.md` — plan and work log (Spanish)
- `DECISIONS.md` — decision record (Spanish)
- `AGENTS.md` — rules that guide the AI agents in this repo

## Data source
Data from the Mercado Público API. **Fuente: Dirección ChileCompra** (Source: Chile's Public Procurement Directorate).
Use is governed by the [API terms of use](https://api.mercadopublico.cl): at most 10,000 requests per day per ticket; bulk downloads are scheduled between 22:00 and 07:00.

---

## 🇨🇱 Resumen en español
Ecosistema de datos de punta a punta sobre las compras públicas de Chile, construido con agentes de IA bajo mi dirección. Las decisiones, validaciones y evaluaciones son mías, y quedan en [`DECISIONS.md`](DECISIONS.md).

- **Pregunta:** ¿quedará desierta esta licitación?, predicha al momento de publicarla. Cerca de 1 de cada 5 licitaciones con resultado queda desierta.
- **Pipeline:** ingesta nocturna en GitHub Actions que respeta las condiciones de uso de la API, warehouse en DuckDB con dbt y un modelo con split temporal y variables sin fuga de información.
- **API:** servicio FastAPI en Docker que entrega la probabilidad, el nivel de riesgo y los tres factores que más pesaron.
- **Resultados:** LightGBM y la regresión logística superan a las dos referencias simples (PR-AUC 0,32 frente a 0,26 y 0,21). Entre el 10% de licitaciones de mayor riesgo, el 40% queda desierta: casi el doble de la tasa base.
- La bitácora ([`docs/ROADMAP.md`](docs/ROADMAP.md)) y las decisiones están en español.

*Fuente de los datos: Dirección ChileCompra.*
