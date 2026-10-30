# Monitoreo del modelo de licitaciones desiertas

Generado: 2026-10-30T18:50:15 · Modelo: 2026-10-24 (6 días)

**No es necesario reentrenar.**

## 1. ¿Cambiaron los datos?
Licitaciones publicadas en los últimos 28 días (2026-10-01 → 2026-10-28, n = 8455) frente a la cohorte de entrenamiento (n = 23643). PSI: < 0.1 estable, 0.1–0.25 vigilar, > 0.25 alerta.

| Variable | PSI | Estado |
|---|---|---|
| tipo | 0.059 | 🟢 estable |
| rubro_principal | 0.034 | 🟢 estable |
| dia_semana_publicacion | 0.019 | 🟢 estable |
| region | 0.012 | 🟢 estable |
| log_monto | 0.010 | 🟢 estable |
| n_items | 0.006 | 🟢 estable |
| hora_publicacion | 0.006 | 🟢 estable |
| monto_desconocido | 0.004 | 🟢 estable |
| moneda | 0.001 | 🟢 estable |
| n_rubros | 0.000 | 🟢 estable |
| convocatoria | 0.000 | 🟢 estable |

## 2. ¿Cambió lo que predice el modelo?
Probabilidad media predicha en la ventana: **21.0%** (tasa base del entrenamiento: 20.5%). Nivel alto: 9.9% de las licitaciones (esperado ≈ 10%).

## 3. ¿Sigue acertando?
8455 predicciones guardadas; 748 ya resueltas. Solo las publicadas hace ≥ 120 días son una evaluación definitiva (las que se resuelven antes están sesgadas hacia desiertas).

| Evaluación | n | Probabilidad media predicha | Tasa observada | ROC-AUC |
|---|---|---|---|---|
| Definitiva (≥ 120 días) | 0 | – | – | – |
| Provisional (sesgada) | 748 | 24.3% | 40.5% | 0.606 |

## Reglas de reentrenamiento
Reentrenar si ocurre cualquiera de estas condiciones: alguna variable con PSI > 0.25; con ≥ 300 evaluaciones definitivas, diferencia entre lo predicho y lo observado > 5%; con ≥ 500 definitivas, ROC-AUC < 0.589 (el baseline tipo × rubro); o un modelo de más de 90 días.

*Fuente de los datos: Dirección ChileCompra.*
