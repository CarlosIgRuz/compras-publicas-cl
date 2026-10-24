from datetime import date

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")
from compras.monitor import reporte as r  # noqa: E402


def poblacion(n=2000, semilla=0, monto_mult=1.0, rubros=("Salud", "Obras", "TI")):
    rng = np.random.default_rng(semilla)
    return pd.DataFrame({
        "codigo": [f"C{semilla}-{i}" for i in range(n)],
        "fecha_publicacion": pd.Timestamp("2026-06-01 10:00") + pd.to_timedelta(rng.integers(0, 600, n), unit="h"),
        "tipo": rng.choice(["LE", "LP", "L1"], n), "convocatoria": "publica",
        "rubro_principal": rng.choice(list(rubros), n), "n_items": rng.integers(1, 20, n), "n_rubros": 1,
        "moneda": "CLP", "region": rng.choice(["RM", "Biobío"], n),
        "monto_estimado_clp": rng.lognormal(16, 1, n) * monto_mult,
    })


def test_psi_estable_y_con_cambio():
    ref = poblacion(semilla=1)
    assert max(r.calcular_drift(ref, poblacion(semilla=2)).values()) < r.PSI_VIGILAR  # misma distribución
    cambio = r.calcular_drift(ref, poblacion(semilla=3, monto_mult=20, rubros=("Obras",)))
    assert cambio["log_monto"] > r.PSI_ALERTA and cambio["rubro_principal"] > r.PSI_ALERTA
    assert cambio["tipo"] < r.PSI_VIGILAR


def test_desempeno_separa_definitivas_de_provisionales():
    hoy = date(2026, 12, 1)
    vieja, nueva = "2026-07-01 10:00:00", "2026-11-20 10:00:00"  # 153 y 11 días
    pred = pd.DataFrame({"codigo": ["A", "B", "C", "D"], "fecha_publicacion": [vieja, vieja, nueva, nueva],
                         "probabilidad": [0.8, 0.1, 0.5, 0.5]})
    resultados = pd.DataFrame({"codigo": ["A", "B", "C"], "es_desierta": [True, False, True]})  # D sigue abierta
    p = r.desempeno(pred, resultados, hoy)
    assert p["predicciones"] == 4 and p["resueltas"] == 3
    assert p["definitivas"] == {"n": 2, "tasa_observada": 0.5, "probabilidad_media": 0.45}
    assert p["provisionales"]["n"] == 1


def test_recomendacion():
    estable = {"tipo": 0.01, "log_monto": 0.05}
    ok = r.recomendacion(estable, {"definitivas": {"n": 0}}, edad_modelo=10)
    assert ok == {"reentrenar": False, "motivos": [], "vigilar": []}

    descal = {"definitivas": {"n": 400, "probabilidad_media": 0.20, "tasa_observada": 0.30, "roc_auc": 0.64}}
    rec = r.recomendacion({"tipo": 0.15, "log_monto": 0.3}, descal, edad_modelo=120)
    assert rec["reentrenar"] and rec["vigilar"] == ["tipo"]
    assert len(rec["motivos"]) == 3  # PSI de log_monto, descalibración y edad

    pocas = {"definitivas": {"n": 100, "probabilidad_media": 0.2, "tasa_observada": 0.5, "roc_auc": 0.5}}
    assert not r.recomendacion(estable, pocas, edad_modelo=10)["reentrenar"]  # muy pocas para concluir


def test_puntuar_limpia_faltantes_y_no_repite(artefactos):
    from compras.api.app import Modelo
    from compras.monitor.puntuar import puntuar

    df = poblacion(n=5)
    df.loc[0, ["tipo", "rubro_principal", "monto_estimado_clp"]] = [None, None, np.nan]
    df["n_items"] = [0, 3, 3, 3, 3]  # sin ítems informados → se trata como 1
    df["codigo_organismo"], df["etapas"], df["monto_visible"] = "ORG1", np.nan, np.nan
    filas = puntuar(df, Modelo(artefactos), excluir={"C0-4"})
    assert [f["codigo"] for f in filas] == ["C0-0", "C0-1", "C0-2", "C0-3"]
    assert all(0 < f["probabilidad"] < 1 and f["nivel"] in {"alto", "medio", "bajo"} for f in filas)
