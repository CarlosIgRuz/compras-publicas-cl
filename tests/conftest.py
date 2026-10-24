"""Fixtures compartidas: artefactos de un modelo entrenado con datos sintéticos."""
import numpy as np
import pytest


@pytest.fixture(scope="session")
def monkeypatch_module():
    m = pytest.MonkeyPatch()
    yield m
    m.undo()


@pytest.fixture(scope="session")
def artefactos(tmp_path_factory, monkeypatch_module):
    pytest.importorskip("lightgbm")
    from compras.models import exportar as ex
    from compras.models import train as t
    from test_train import datos_sinteticos

    df = datos_sinteticos(n=2000)
    df["codigo_organismo"] = np.where(df.index % 2 == 0, "ORG1", "ORG2")
    res = t.evaluar(df)
    pred = res.pop("_pred_test_lightgbm")
    res.pop("_modelo_lightgbm")
    destino = tmp_path_factory.mktemp("modelo")
    hist = ({"ORG1": {"n": 40, "desiertas": 20, "nombre": "Organismo Uno"}},
            {"Obras": {"n": 100, "desiertas": 40}})
    monkeypatch_module.setattr(ex, "historiales", lambda db: hist)
    ex.exportar(df, res, pred, db=None, destino=destino)
    return destino
