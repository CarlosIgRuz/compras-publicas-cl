@echo off
REM Descarga incremental de licitaciones (ejecutar en Windows; ideal programarlo entre 22:00 y 07:00).
REM Uso: descargar.bat 2026-04-01 2026-10-13   (sin argumentos: solo ayer)
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install -q requests python-dotenv
)
set PYTHONPATH=src
if "%~1"=="" (
  for /f %%d in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set AYER=%%d
  .venv\Scripts\python -m compras.ingest.extract --desde %AYER% --hasta %AYER% >> data\ingesta.log 2>&1
) else (
  .venv\Scripts\python -m compras.ingest.extract --desde %1 --hasta %2
)
