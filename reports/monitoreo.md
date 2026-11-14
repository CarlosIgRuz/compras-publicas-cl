# Monitoreo del modelo de licitaciones desiertas

Generado: 2026-11-14T18:51:24 · Modelo: 2026-10-24 (21 días)

**No es necesario reentrenar.**

## 1. ¿Cambiaron los datos?
Licitaciones publicadas en los últimos 28 días (2026-10-16 → 2026-11-12, n = 9508) frente a la cohorte de entrenamiento (n = 27263). PSI: < 0.1 estable, 0.1–0.25 vigilar, > 0.25 alerta.

| Variable | PSI | Estado |
|---|---|---|
| rubro_principal | 0.028 | 🟢 estable |
| tipo | 0.027 | 🟢 estable |
| dia_semana_publicacion | 0.011 | 🟢 estable |
| log_monto | 0.007 | 🟢 estable |
| region | 0.007 | 🟢 estable |
| hora_publicacion | 0.005 | 🟢 estable |
| monto_desconocido | 0.003 | 🟢 estable |
| n_items | 0.003 | 🟢 estable |
| moneda | 0.000 | 🟢 estable |
| convocatoria | 0.000 | 🟢 estable |
| n_rubros | 0.000 | 🟢 estable |

## 2. ¿Cambió lo que predice el modelo?
Probabilidad media predicha en la ventana: **20.8%** (tasa base del entrenamiento: 20.5%). Nivel alto: 10.3% de las licitaciones (esperado ≈ 10%).

## 3. ¿Sigue acertando?
13695 predicciones guardadas; 3067 ya resueltas. Solo las publicadas hace ≥ 120 días son una evaluación definitiva (las que se resuelven antes están sesgadas hacia desiertas).

| Evaluación | n | Probabilidad media predicha | Tasa observada | ROC-AUC |
|---|---|---|---|---|
| Definitiva (≥ 120 días) | 0 | – | – | – |
| Provisional (sesgada) | 3067 | 23.2% | 29.8% | 0.631 |

## Reglas de reentrenamiento
Reentrenar si ocurre cualquiera de estas condiciones: alguna variable con PSI > 0.25; con ≥ 300 evaluaciones definitivas, diferencia entre lo predicho y lo observado > 5%; con ≥ 500 definitivas, ROC-AUC < 0.589 (el baseline tipo × rubro); o un modelo de más de 90 días.

*Fuente de los datos: Dirección ChileCompra.*
