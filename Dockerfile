# API de predicción: riesgo de que una licitación quede desierta.
# Fuente de los datos: Dirección ChileCompra.
FROM python:3.11-slim

# LightGBM necesita OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/compras/__init__.py src/compras/__init__.py
COPY src/compras/api src/compras/api
COPY artifacts/modelo artifacts/modelo

ENV PYTHONPATH=/app/src MODELO_DIR=/app/artifacts/modelo PORT=8000
RUN useradd --create-home api
USER api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/health')"
CMD ["sh", "-c", "uvicorn compras.api.app:app --host 0.0.0.0 --port ${PORT}"]
