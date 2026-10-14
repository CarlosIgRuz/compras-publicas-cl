# Instrucciones para agentes en este repo

Al iniciar una sesión, lee primero `docs/ROADMAP.md` (estado actual y siguiente tarea) y `DECISIONS.md`.

## Reglas
- Nunca escribir el ticket de la API ni otros secretos en el código, logs o commits: siempre desde `.env` (`MERCADO_PUBLICO_TICKET`).
- Respetar las condiciones de uso de la API: máximo 10.000 requests/día por ticket (nunca eludirlo), cachear en `data/raw/` sin repetir descargas, y ejecutar descargas masivas solo entre 22:00 y 07:00 (hora de Chile).
- Toda publicación de datos (README, demo, gráficos) debe indicar "Fuente: Dirección ChileCompra".
- Datos crudos nunca se modifican; toda limpieza va en dbt (`dbt/models/staging`).
- Todo código nuevo lleva al menos un test en `tests/`; `pytest` debe pasar antes de commitear.
- Métricas de modelos: siempre comparar contra un baseline simple y reportar varias métricas (no solo accuracy).
- Al terminar una sesión: actualizar la bitácora en `docs/ROADMAP.md` y registrar decisiones en `DECISIONS.md`.
- Commits pequeños, mensajes en español, formato `tipo: descripción` (feat, fix, data, docs, test).
