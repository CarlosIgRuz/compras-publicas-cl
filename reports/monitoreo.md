# Monitoreo del modelo de licitaciones desiertas

Generado: 2026-10-26T19:33:22 · Modelo: 2026-10-24 (2 días)

**No es necesario reentrenar.**

## 1. ¿Cambiaron los datos?
Licitaciones publicadas en los últimos 28 días (2026-10-01 → 2026-10-24, n = 7075) frente a la cohorte de entrenamiento (n = 22992). PSI: < 0.1 estable, 0.1–0.25 vigilar, > 0.25 alerta.

| Variable | PSI | Estado |
|---|---|---|
| dia_semana_publicacion | 0.074 | 🟢 estable |
| tipo | 0.070 | 🟢 estable |
| rubro_principal | 0.039 | 🟢 estable |
| region | 0.013 | 🟢 estable |
| log_monto | 0.012 | 🟢 estable |
| n_items | 0.007 | 🟢 estable |
| hora_publicacion | 0.004 | 🟢 estable |
| monto_desconocido | 0.004 | 🟢 estable |
| moneda | 0.001 | 🟢 estable |
| n_rubros | 0.000 | 🟢 estable |
| convocatoria | 0.000 | 🟢 estable |

## 2. ¿Cambió lo que predice el modelo?
Probabilidad media predicha en la ventana: **20.9%** (tasa base del entrenamiento: 20.5%). Nivel alto: 9.5% de las licitaciones (esperado ≈ 10%).

## 3. ¿Sigue acertando?
7075 predicciones guardadas; 489 ya resueltas. Solo las publicadas hace ≥ 120 días son una evaluación definitiva (las que se resuelven antes están sesgadas hacia desiertas).

| Evaluación | n | Probabilidad media predicha | Tasa observada | ROC-AUC |
|---|---|---|---|---|
| Definitiva (≥ 120 días) | 0 | – | – | – |
| Provisional (sesgada) | 489 | 24.7% | 41.9% | 0.599 |

## Reglas de reentrenamiento
Reentrenar si ocurre cualquiera de estas condiciones: alguna variable con PSI > 0.25; con ≥ 300 evaluaciones definitivas, diferencia entre lo predicho y lo observado > 5%; con ≥ 500 definitivas, ROC-AUC < 0.589 (el baseline tipo × rubro); o un modelo de más de 90 días.

*Fuente de los datos: Dirección ChileCompra.*
