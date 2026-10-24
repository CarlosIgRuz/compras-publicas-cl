"""Exporta el modelo de servicio que usa la API (P1.8).

Contenido de la carpeta de artefactos:
- `lightgbm.txt`: LightGBM reentrenado con TODA la cohorte (mismo n° de árboles que eligió el
  early stopping, escalado por el tamaño de los datos).
- `metadata.json`: variables, categorías conocidas, suavizado del historial, umbrales de riesgo
  y métricas de prueba del modelo evaluado.
- `historial_organismos.json` / `historial_rubros.json`: licitaciones resueltas y desiertas por
  organismo y por rubro, para calcular el historial al momento de predecir.

Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import train as t

SUAVIZADO_M = 10
TASA_PREVIA_P0 = 0.207  # igual que en dbt (vars suavizado_m / tasa_previa_p0)


def entrenar_final(df: pd.DataFrame, n_arboles: int):
    """LightGBM con todos los datos de la cohorte y un n° fijo de árboles (sin early stopping)."""
    import lightgbm as lgb

    X = t.preparar(df)
    categorias = {c: sorted(X[c].unique()) for c in t.CATEGORICAS}
    for c in t.CATEGORICAS:
        X[c] = t.a_categoria(X[c], categorias[c])
    modelo = lgb.LGBMClassifier(
        n_estimators=n_arboles, learning_rate=0.03, num_leaves=31, min_child_samples=40,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
        random_state=t.SEMILLA, verbose=-1,
    )
    modelo.fit(X, df[t.OBJETIVO].astype(int))
    return modelo, categorias


def historiales(db: Path) -> tuple[dict, dict]:
    """Conteos de licitaciones resueltas y desiertas por organismo y por rubro (todas las fechas)."""
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    org = con.execute("""
        select codigo_organismo, count(*), sum(es_desierta::int), arg_max(organismo, fecha_publicacion)
        from fct_licitaciones where tiene_resultado and codigo_organismo is not null group by 1
    """).fetchall()
    rub = con.execute("""
        select rubro_principal, count(*), sum(es_desierta::int)
        from fct_licitaciones where tiene_resultado and rubro_principal is not null group by 1
    """).fetchall()
    con.close()
    return ({c: {"n": int(n), "desiertas": int(d), "nombre": nom} for c, n, d, nom in org},
            {r: {"n": int(n), "desiertas": int(d)} for r, n, d in rub})


def exportar(df: pd.DataFrame, res: dict, pred_test: np.ndarray, db: Path, destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    escala = len(df) / max(1, res["n"]["train"])
    n_arboles = max(50, int(round(res["lightgbm_iteraciones"] * escala)))
    modelo, categorias = entrenar_final(df, n_arboles)
    modelo.booster_.save_model(str(destino / "lightgbm.txt"))

    org, rub = historiales(db)
    (destino / "historial_organismos.json").write_text(json.dumps(org, ensure_ascii=False), encoding="utf-8")
    (destino / "historial_rubros.json").write_text(json.dumps(rub, ensure_ascii=False), encoding="utf-8")

    m = res["modelos"]["lightgbm"]
    meta = {
        "version": datetime.now().strftime("%Y-%m-%d"),
        "objetivo": "probabilidad de que la licitación quede desierta, predicha al publicar",
        "categoricas": t.CATEGORICAS,
        "numericas": t.NUMERICAS,
        "categorias": categorias,
        "n_arboles": n_arboles,
        "suavizado": {"m": SUAVIZADO_M, "p0": TASA_PREVIA_P0},
        "tasa_base": res["tasa_desierta"]["test"],
        # umbrales calibrados en la prueba del modelo evaluado (datos que no vio al entrenar)
        "umbrales": {"alto": float(np.quantile(pred_test, 0.90)), "medio": res["tasa_desierta"]["test"]},
        "metricas_prueba": {k: m[k] for k in ("pr_auc", "roc_auc", "brier", "precision_top10")},
        "datos": {"cohorte": [res["periodos"]["train"][0], res["periodos"]["test"][1]],
                  "n_entrenamiento_final": len(df)},
        "fuente": "Dirección ChileCompra",
    }
    (destino / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino
