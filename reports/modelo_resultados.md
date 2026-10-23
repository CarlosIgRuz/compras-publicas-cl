# Resultados del modelo: ¿quedará desierta la licitación?

Generado: 2026-10-23T07:35:01 · Cohorte: publicadas 2026-04-01 → 2026-06-23

| Partición | n | Período de publicación | % desiertas |
|---|---|---|---|
| Entrenamiento | 15299 | 2026-04-01 → 2026-06-01 | 20.6% |
| Validación | 3278 | 2026-06-01 → 2026-06-11 | 20.7% |
| Prueba | 3279 | 2026-06-11 → 2026-06-23 | 20.5% |

## Métricas en prueba

| Modelo | PR-AUC [IC 95%] | ROC-AUC | Brier | Recall a precisión 50% | % desiertas en el 10% de mayor riesgo |
|---|---|---|---|---|---|
| baseline_tasa_global | 0.205 | 0.500 | 0.1629 | 0.000 | 20.5% |
| baseline_tipo_x_rubro | 0.264 [0.240–0.294] | 0.589 | 0.1600 | 0.012 | 29.9% |
| regresion_logistica | 0.317 [0.290–0.349] | 0.634 | 0.1560 | 0.064 | 37.8% |
| lightgbm | 0.317 [0.289–0.351] | 0.643 | 0.1567 | 0.068 | 39.6% |

## Variables más importantes (LightGBM, ganancia)

| Variable | Ganancia |
|---|---|
| rubro_principal | 21.9% |
| n_items | 19.5% |
| org_tasa_desierta_previa | 14.2% |
| log_monto_estimado_clp | 8.7% |
| convocatoria | 7.1% |
| region | 7.0% |
| org_n_previas | 5.9% |
| rubro_tasa_desierta_previa | 4.5% |
| rubro_n_previas | 4.2% |
| tipo | 2.8% |
| hora_publicacion | 1.7% |
| dia_semana_publicacion | 1.2% |
| n_rubros | 0.6% |
| etapas | 0.5% |
| monto_visible | 0.1% |

*Fuente de los datos: Dirección ChileCompra.*
