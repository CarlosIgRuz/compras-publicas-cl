import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("lightgbm")
from fastapi.testclient import TestClient  # noqa: E402

from compras.models import train as t  # noqa: E402


@pytest.fixture(scope="session")
def cliente(artefactos, monkeypatch_module):
    from compras.api import app as api

    monkeypatch_module.setenv("MODELO_DIR", str(artefactos))
    api.modelo.cache_clear()
    return TestClient(api.app)


def test_health_y_modelo(cliente):
    assert cliente.get("/health").json()["estado"] == "ok"
    info = cliente.get("/modelo").json()
    assert info["fuente"] == "Dirección ChileCompra" and "alto" in info["umbrales"]


def test_predecir(cliente):
    r = cliente.post("/predecir", json={"tipo": "L1", "rubro_principal": "Obras", "n_items": 25,
                                        "codigo_organismo": "ORG1", "monto_estimado_clp": 5e6,
                                        "fecha_publicacion": "2026-06-15T10:00:00"})
    assert r.status_code == 200
    j = r.json()
    assert 0 < j["probabilidad_desierta"] < 1 and j["nivel"] in {"alto", "medio", "bajo"}
    assert 1 <= len(j["factores"]) <= 3
    assert j["historial_organismo"] == {"conocido": True, "nombre": "Organismo Uno",
                                        "licitaciones_resueltas": 40,
                                        "tasa_desierta_suavizada": round((20 + 10 * 0.207) / 50, 4)}


def test_riesgo_sube_con_la_senal(cliente):
    def p(**kw):
        base = {"tipo": "LP", "rubro_principal": "Salud", "n_items": 1, "fecha_publicacion": "2026-06-15T10:00:00"}
        return cliente.post("/predecir", json={**base, **kw}).json()["probabilidad_desierta"]

    assert p(rubro_principal="Obras", n_items=29, tipo="L1") > p()


def test_valores_desconocidos_y_validacion(cliente):
    ok = cliente.post("/predecir", json={"tipo": "ZZ", "rubro_principal": "Nunca visto", "n_items": 2})
    assert ok.status_code == 200 and ok.json()["historial_organismo"]["conocido"] is False
    assert cliente.post("/predecir", json={"tipo": "LE", "n_items": 0}).status_code == 422
    assert cliente.post("/predecir", json={"tipo": "LE", "n_items": 1, "n_rubros": 3}).status_code == 422


def test_variables_de_la_api_igual_que_en_entrenamiento(artefactos):
    """Evita el desfase entrenamiento/servicio: misma fila → mismas variables."""
    from compras.api.app import Licitacion, Modelo

    m = Modelo(artefactos)
    lic = Licitacion(tipo="LE", rubro_principal="Obras", n_items=4, n_rubros=2, region="RM",
                     codigo_organismo="ORG1", etapas=1, monto_estimado_clp=1e7, monto_visible=True,
                     fecha_publicacion="2026-06-17T15:30:00")
    api = m.variables(lic)
    fila = pd.DataFrame([{
        "tipo": "LE", "convocatoria": "publica", "rubro_principal": "Obras", "moneda": "CLP", "region": "RM",
        "etapas": 1, "dia_semana_publicacion": 3, "hora_publicacion": 15, "n_items": 4, "n_rubros": 2,
        "monto_visible": True, "monto_desconocido": False, "log_monto_estimado_clp": np.log1p(1e7),
        "org_n_previas": 40, "org_tasa_desierta_previa": (20 + 2.07) / 50,
        "rubro_n_previas": 100, "rubro_tasa_desierta_previa": (40 + 2.07) / 110,
    }])
    entreno = t.preparar(fila)
    for c in t.CATEGORICAS:
        entreno[c] = t.a_categoria(entreno[c], m.meta["categorias"][c])
    pd.testing.assert_frame_equal(api.reset_index(drop=True), entreno[api.columns].reset_index(drop=True),
                                  check_dtype=False)


def test_pagina_demo_y_organismos(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Dirección ChileCompra" in r.text
    orgs = cliente.get("/organismos").json()
    assert orgs == [{"codigo": "ORG1", "nombre": "Organismo Uno", "licitaciones": 40}]


def test_carpeta_del_space_tiene_lo_necesario(tmp_path):
    from pathlib import Path

    from compras.deploy.space import preparar

    raiz = Path(__file__).resolve().parents[1]
    c = preparar(tmp_path / "space", raiz)
    for f in ["Dockerfile", "README.md", "requirements-api.txt", "src/compras/api/app.py",
              "src/compras/api/static/index.html", "artifacts/modelo/lightgbm.txt", "artifacts/modelo/metadata.json"]:
        assert (c / f).exists(), f
    assert "sdk: docker" in (c / "README.md").read_text() and "app_port: 8000" in (c / "README.md").read_text()
    assert not list(c.rglob("__pycache__"))
