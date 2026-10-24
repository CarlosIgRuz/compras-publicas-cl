# Monitoreo del modelo de licitaciones desiertas

Generado: 2026-10-24T16:56:49 · Modelo: 2026-10-24 (0 días)

**No es necesario reentrenar.**

## 1. ¿Cambiaron los datos?
Licitaciones publicadas en los últimos 28 días (2026-10-01 → 2026-10-21, n = 6062) frente a la cohorte de entrenamiento (n = 22639). PSI: < 0.1 estable, 0.1–0.25 vigilar, > 0.25 alerta.

| Variable | PSI | Estado |
|---|---|---|
| tipo | 0.073 | 🟢 estable |
| rubro_principal | 0.043 | 🟢 estable |
| dia_semana_publicacion | 0.030 | 🟢 estable |
| log_monto | 0.012 | 🟢 estable |
| region | 0.012 | 🟢 estable |
| n_items | 0.007 | 🟢 estable |
| hora_publicacion | 0.006 | 🟢 estable |
| monto_desconocido | 0.003 | 🟢 estable |
| moneda | 0.001 | 🟢 estable |
| n_rubros | 0.000 | 🟢 estable |
| convocatoria | 0.000 | 🟢 estable |

## 2. ¿Cambió lo que predice el modelo?
Probabilidad media predicha en la ventana: **21.0%** (tasa base del entrenamiento: 20.5%). Nivel alto: 9.5% de las licitaciones (esperado ≈ 10%).

## 3. ¿Sigue acertando?
6062 predicciones guardadas; 267 ya resueltas. Solo las publicadas hace ≥ 120 días son una evaluación definitiva (las que se resuelven antes están sesgadas hacia desiertas).

| Evaluación | n | Probabilidad media predicha | Tasa observada | ROC-AUC |
|---|---|---|---|---|
| Definitiva (≥ 120 días) | 0 | – | – | – |
| Provisional (sesgada) | 267 | 26.2% | 52.1% | 0.630 |

## Reglas de reentrenamiento
Reentrenar si ocurre cualquiera de estas condiciones: alguna variable con PSI > 0.25; con ≥ 300 evaluaciones definitivas, diferencia entre lo predicho y lo observado > 5%; con ≥ 500 definitivas, ROC-AUC < 0.589 (el baseline tipo × rubro); o un modelo de más de 90 días.

*Fuente de los datos: Dirección ChileCompra.*
