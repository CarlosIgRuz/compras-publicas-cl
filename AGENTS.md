# Instrucciones para agentes en este repo

Al iniciar una sesión, lee primero `docs/ROADMAP.md` (estado actual y siguiente tarea) y `DECISIONS.md`.

## Reglas
- Nunca escribir el ticket de la API ni otros secretos en el código, logs o commits: siempre desde `.env` (`MERCADO_PUBLICO_TICKET`).
- Respetar el límite de 10.000 requests/día de la API: cachear respuestas en `data/raw/` y no repetir descargas.
- Datos crudos nunca se modifican; toda limpieza va en dbt (`dbt/models/staging`).
- Todo código nuevo lleva al menos un test en `tests/`; `pytest` debe pasar antes de commitear.
- Métricas de modelos: siempre comparar contra un baseline simple y reportar varias métricas (no solo accuracy).
- Al terminar una sesión: actualizar la bitácora en `docs/ROADMAP.md` y registrar decisiones en `DECISIONS.md`.
- Commits pequeños, mensajes en español, formato `tipo: descripción` (feat, fix, data, docs, test).
