import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")
from compras.models import train as t  # noqa: E402


def datos_sinteticos(n=3000, semilla=0):
    rng = np.random.default_rng(semilla)
    rubro = rng.choice(["Salud", "Obras", "TI"], n)
    tipo = rng.choice(["L1", "LE", "LP"], n)
    n_items = rng.integers(1, 30, n)
    # señal: obras y muchos ítems → más desiertas
    logit = -1.6 + 1.2 * (rubro == "Obras") + 0.05 * n_items + 0.6 * (tipo == "L1")
    y = rng.random(n) < 1 / (1 + np.exp(-logit))
    df = pd.DataFrame({
        "codigo": [f"C{i}" for i in range(n)],
        "fecha_publicacion": pd.Timestamp("2026-04-01") + pd.to_timedelta(rng.integers(0, 80, n), unit="D"),
        "es_desierta": y, "tipo": tipo, "convocatoria": "publica", "rubro_principal": rubro,
        "moneda": "CLP", "region": rng.choice(["RM", "Biobío"], n), "n_items": n_items,
    })
    for c in t.NUMERICAS:
        if c not in df:
            df[c] = rng.random(n)
    return df


def test_split_temporal_no_mezcla_el_futuro():
    p = t.split_temporal(datos_sinteticos())
    assert p.train.fecha_publicacion.max() <= p.valid.fecha_publicacion.min()
    assert p.valid.fecha_publicacion.max() <= p.test.fecha_publicacion.min()
    assert len(p.train) + len(p.valid) + len(p.test) == 3000


def test_modelos_superan_baseline_global():
    res = t.evaluar(datos_sinteticos())
    m = res["modelos"]
    assert m["baseline_tasa_global"]["roc_auc"] == 0.5
    assert m["lightgbm"]["pr_auc"] > m["baseline_tasa_global"]["pr_auc"] + 0.05
    assert m["regresion_logistica"]["roc_auc"] > 0.6
    assert {"pr_auc_ic95", "roc_auc_ic95"} <= set(m["lightgbm"])
    assert res["importancias_lightgbm"][0][0] in {"rubro_principal", "n_items", "tipo"}


def test_categoria_no_vista_no_rompe_la_prediccion():
    df = datos_sinteticos()
    p = t.split_temporal(df)
    modelo = t.entrenar_lightgbm(p.train, p.valid)
    nuevo = p.test.head(5).copy()
    nuevo["rubro_principal"] = "Rubro nunca visto"
    assert np.isfinite(t.predecir_lightgbm(modelo, nuevo)).all()


def test_baseline_tipo_rubro_suaviza_hacia_la_tasa_global():
    train = pd.DataFrame({"tipo": ["A"] * 2, "rubro_principal": ["X"] * 2, "es_desierta": [1, 1]})
    otro = pd.DataFrame({"tipo": ["A", "B"], "rubro_principal": ["X", "Y"]})
    p = t.baseline_tipo_rubro(train, otro, m=2)
    assert p[0] == pytest.approx((2 + 2 * 1.0) / 4)  # grupo conocido
    assert p[1] == pytest.approx(1.0)                # grupo desconocido → tasa global
