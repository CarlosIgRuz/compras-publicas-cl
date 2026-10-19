# Resultados del modelo: ¿quedará desierta la licitación?

> **Preliminar:** el detalle cubre el 46% de las licitaciones resueltas; la cohorte aún está sesgada hacia resultados rápidos. Se re-entrena al completar la descarga.

Generado: 2026-10-19T06:52:43 · Cohorte: publicadas 2026-04-01 → 2026-06-19

| Partición | n | Período de publicación | % desiertas |
|---|---|---|---|
| Entrenamiento | 9319 | 2026-04-01 → 2026-05-14 | 21.6% |
| Validación | 1997 | 2026-05-14 → 2026-05-28 | 24.2% |
| Prueba | 1997 | 2026-05-28 → 2026-06-19 | 30.5% |

## Métricas en prueba

| Modelo | PR-AUC [IC 95%] | ROC-AUC | Brier | Recall a precisión 50% |
|---|---|---|---|---|
| baseline_tasa_global | 0.305 | 0.500 | 0.2194 | 0.000 |
| baseline_tipo_x_rubro | 0.355 [0.325–0.391] | 0.565 | 0.2173 | 0.000 |
| regresion_logistica | 0.442 [0.403–0.482] | 0.625 | 0.2055 | 0.215 |
| lightgbm | 0.422 [0.387–0.463] | 0.622 | 0.2172 | 0.157 |

## Variables más importantes (LightGBM, ganancia)

| Variable | Ganancia |
|---|---|
| rubro_principal | 25.2% |
| n_items | 16.1% |
| org_tasa_desierta_previa | 12.6% |
| log_monto_estimado_clp | 10.8% |
| convocatoria | 10.2% |
| region | 4.5% |
| rubro_n_previas | 4.3% |
| rubro_tasa_desierta_previa | 3.7% |
| org_n_previas | 3.1% |
| hora_publicacion | 2.9% |
| dias_abierta | 2.6% |
| tipo | 1.9% |
| etapas | 1.6% |
| dia_semana_publicacion | 0.5% |
| monto_visible | 0.0% |

*Fuente de los datos: Dirección ChileCompra.*
