# Monitoreo del modelo de licitaciones desiertas

Generado: 2026-11-10T20:37:00 · Modelo: 2026-10-24 (17 días)

**No es necesario reentrenar.**

## 1. ¿Cambiaron los datos?
Licitaciones publicadas en los últimos 28 días (2026-10-12 → 2026-11-07, n = 9022) frente a la cohorte de entrenamiento (n = 26074). PSI: < 0.1 estable, 0.1–0.25 vigilar, > 0.25 alerta.

| Variable | PSI | Estado |
|---|---|---|
| tipo | 0.042 | 🟢 estable |
| rubro_principal | 0.029 | 🟢 estable |
| dia_semana_publicacion | 0.015 | 🟢 estable |
| region | 0.009 | 🟢 estable |
| hora_publicacion | 0.006 | 🟢 estable |
| log_monto | 0.005 | 🟢 estable |
| n_items | 0.003 | 🟢 estable |
| monto_desconocido | 0.003 | 🟢 estable |
| moneda | 0.001 | 🟢 estable |
| convocatoria | 0.000 | 🟢 estable |
| n_rubros | 0.000 | 🟢 estable |

## 2. ¿Cambió lo que predice el modelo?
Probabilidad media predicha en la ventana: **20.7%** (tasa base del entrenamiento: 20.5%). Nivel alto: 9.7% de las licitaciones (esperado ≈ 10%).

## 3. ¿Sigue acertando?
11790 predicciones guardadas; 2281 ya resueltas. Solo las publicadas hace ≥ 120 días son una evaluación definitiva (las que se resuelven antes están sesgadas hacia desiertas).

| Evaluación | n | Probabilidad media predicha | Tasa observada | ROC-AUC |
|---|---|---|---|---|
| Definitiva (≥ 120 días) | 0 | – | – | – |
| Provisional (sesgada) | 2281 | 23.3% | 31.2% | 0.632 |

## Reglas de reentrenamiento
Reentrenar si ocurre cualquiera de estas condiciones: alguna variable con PSI > 0.25; con ≥ 300 evaluaciones definitivas, diferencia entre lo predicho y lo observado > 5%; con ≥ 500 definitivas, ROC-AUC < 0.589 (el baseline tipo × rubro); o un modelo de más de 90 días.

*Fuente de los datos: Dirección ChileCompra.*
