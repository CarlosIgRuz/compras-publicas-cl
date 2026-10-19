"""Entrena y evalúa el modelo de "licitación desierta" (P1.7).

Objetivo: `es_desierta`, predicho al momento de publicar (ver DECISIONS.md).
Datos: `ml_licitaciones` del warehouse (cohorte sin sesgo de selección, `en_cohorte`).
Split temporal por fecha de publicación: entrenamiento → validación → prueba.
Modelos: dos baselines (tasa global y tasa histórica por tipo × rubro), regresión logística
y LightGBM. Métricas en prueba: PR-AUC, ROC-AUC, Brier y recall a precisión fija, con
intervalos bootstrap.

Uso: python -m compras.models.train [--db data/warehouse.duckdb] [--salida reports]
Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

OBJETIVO = "es_desierta"
CATEGORICAS = ["tipo", "convocatoria", "rubro_principal", "moneda", "region"]
NUMERICAS = [
    "etapas", "dias_abierta", "dia_semana_publicacion", "hora_publicacion",
    "n_items", "n_rubros", "monto_visible", "monto_desconocido", "log_monto_estimado_clp",
    "org_n_previas", "org_tasa_desierta_previa", "rubro_n_previas", "rubro_tasa_desierta_previa",
]
# Excluidas a propósito: mes_publicacion (en un split temporal es un proxy del tiempo y no
# generaliza), codigo_organismo (alta cardinalidad; su historial ya entra point-in-time).
PRECISION_OBJETIVO = 0.5
SEMILLA = 42


@dataclass
class Particion:
    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame


def cargar(db: Path) -> pd.DataFrame:
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    df = con.sql(
        f"select * from ml_licitaciones where en_cohorte and {OBJETIVO} is not null order by fecha_publicacion, codigo"
    ).df()
    con.close()
    return df


def split_temporal(df: pd.DataFrame, frac_valid: float = 0.15, frac_test: float = 0.15) -> Particion:
    """Ordena por fecha de publicación y corta en bloques consecutivos (sin mezclar el futuro)."""
    df = df.sort_values(["fecha_publicacion", "codigo"]).reset_index(drop=True)
    n = len(df)
    i_valid = int(n * (1 - frac_valid - frac_test))
    i_test = int(n * (1 - frac_test))
    return Particion(df.iloc[:i_valid], df.iloc[i_valid:i_test], df.iloc[i_test:])


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    X = df[CATEGORICAS + NUMERICAS].copy()
    for c in CATEGORICAS:
        X[c] = X[c].fillna("desconocido").astype(str)
    for c in NUMERICAS:
        X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    return X


# ---------- modelos ----------

def baseline_global(train: pd.DataFrame, otro: pd.DataFrame) -> np.ndarray:
    return np.full(len(otro), train[OBJETIVO].mean())


def baseline_tipo_rubro(train: pd.DataFrame, otro: pd.DataFrame, m: float = 20) -> np.ndarray:
    """Tasa histórica (del entrenamiento) por tipo × rubro, suavizada hacia la tasa global."""
    p0 = train[OBJETIVO].mean()
    g = train.groupby(["tipo", "rubro_principal"], dropna=False)[OBJETIVO].agg(["sum", "count"])
    tasa = ((g["sum"] + m * p0) / (g["count"] + m)).rename("tasa")
    unido = otro[["tipo", "rubro_principal"]].merge(tasa, left_on=["tipo", "rubro_principal"], right_index=True, how="left")
    return unido["tasa"].fillna(p0).to_numpy()


def entrenar_logistica(train: pd.DataFrame):
    prep = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAS),
        ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUMERICAS),
    ])
    modelo = make_pipeline(prep, LogisticRegression(max_iter=2000, C=0.5))
    modelo.fit(preparar(train), train[OBJETIVO].astype(int))
    return modelo


def a_categoria(serie: pd.Series, categorias: list[str]) -> pd.Categorical:
    """Valores no vistos en entrenamiento → NaN (LightGBM los trata como faltantes)."""
    return pd.Categorical(serie.where(serie.isin(categorias)), categories=categorias)


def entrenar_lightgbm(train: pd.DataFrame, valid: pd.DataFrame):
    import lightgbm as lgb

    Xtr, Xva = preparar(train), preparar(valid)
    categorias = {c: sorted(Xtr[c].unique()) for c in CATEGORICAS}
    for X in (Xtr, Xva):
        for c in CATEGORICAS:
            X[c] = a_categoria(X[c], categorias[c])
    modelo = lgb.LGBMClassifier(
        n_estimators=2000, learning_rate=0.03, num_leaves=31, min_child_samples=40,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
        random_state=SEMILLA, verbose=-1,
    )
    modelo.fit(
        Xtr, train[OBJETIVO].astype(int), eval_set=[(Xva, valid[OBJETIVO].astype(int))],
        eval_metric="average_precision", callbacks=[lgb.early_stopping(100, verbose=False)],
    )
    modelo.categorias_ = categorias
    return modelo


def predecir_lightgbm(modelo, df: pd.DataFrame) -> np.ndarray:
    X = preparar(df)
    for c in CATEGORICAS:
        X[c] = a_categoria(X[c], modelo.categorias_[c])
    return modelo.predict_proba(X)[:, 1]


# ---------- métricas ----------

def recall_a_precision(y: np.ndarray, p: np.ndarray, precision_min: float = PRECISION_OBJETIVO) -> float:
    prec, rec, _ = precision_recall_curve(y, p)
    ok = rec[prec >= precision_min]
    return float(ok.max()) if len(ok) else 0.0


def metricas(y: np.ndarray, p: np.ndarray) -> dict:
    y = np.asarray(y).astype(int)
    unica = len(np.unique(p)) == 1  # baseline constante: ROC/PR no informativos más allá del azar
    return {
        "pr_auc": float(y.mean()) if unica else float(average_precision_score(y, p)),
        "roc_auc": 0.5 if unica else float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        f"recall_a_precision_{int(PRECISION_OBJETIVO * 100)}": 0.0 if unica else recall_a_precision(y, p),
    }


def intervalo_bootstrap(y: np.ndarray, p: np.ndarray, n: int = 300) -> dict:
    """IC 95% bootstrap para PR-AUC y ROC-AUC en prueba."""
    rng = np.random.default_rng(SEMILLA)
    y, p = np.asarray(y).astype(int), np.asarray(p)
    pr, roc = [], []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        pr.append(average_precision_score(y[i], p[i]))
        roc.append(roc_auc_score(y[i], p[i]))
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    return {"pr_auc_ic95": q(pr), "roc_auc_ic95": q(roc)}


def importancias(modelo, top: int = 15) -> list[tuple[str, float]]:
    gan = modelo.booster_.feature_importance(importance_type="gain")
    nombres = modelo.booster_.feature_name()
    total = gan.sum() or 1.0
    orden = np.argsort(gan)[::-1][:top]
    return [(nombres[i], round(float(gan[i] / total), 4)) for i in orden]


# ---------- orquestación ----------

def evaluar(df: pd.DataFrame) -> dict:
    part = split_temporal(df)
    yte = part.test[OBJETIVO].astype(int).to_numpy()

    lgbm = entrenar_lightgbm(part.train, part.valid)
    # para los demás modelos, validación y entrenamiento juntos (no necesitan early stopping)
    tv = pd.concat([part.train, part.valid])
    logit = entrenar_logistica(tv)

    predicciones = {
        "baseline_tasa_global": baseline_global(tv, part.test),
        "baseline_tipo_x_rubro": baseline_tipo_rubro(tv, part.test),
        "regresion_logistica": logit.predict_proba(preparar(part.test))[:, 1],
        "lightgbm": predecir_lightgbm(lgbm, part.test),
    }
    resultados = {nombre: metricas(yte, p) for nombre, p in predicciones.items()}
    for nombre in ("baseline_tipo_x_rubro", "regresion_logistica", "lightgbm"):
        resultados[nombre].update(intervalo_bootstrap(yte, predicciones[nombre]))

    def rango(d):
        return [str(pd.Timestamp(d.fecha_publicacion.min()).date()), str(pd.Timestamp(d.fecha_publicacion.max()).date())]

    return {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "n": {"train": len(part.train), "valid": len(part.valid), "test": len(part.test)},
        "periodos": {"train": rango(part.train), "valid": rango(part.valid), "test": rango(part.test)},
        "tasa_desierta": {k: float(getattr(part, k)[OBJETIVO].mean()) for k in ("train", "valid", "test")},
        "modelos": resultados,
        "lightgbm_iteraciones": int(lgbm.best_iteration_ or lgbm.n_estimators),
        "importancias_lightgbm": importancias(lgbm),
        "_modelo_lightgbm": lgbm,
    }


def completitud_detalle(db: Path) -> float:
    """Fracción de licitaciones resueltas en los listados que ya tienen detalle descargado."""
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    v = con.sql("""
        select avg((d.codigo is not null)::int)
        from (select distinct codigo from stg_listados
              where estado in ('desierta','adjudicada','revocada','suspendida')) l
        left join stg_detalle d using (codigo)
    """).fetchone()[0]
    con.close()
    return float(v)


def reporte_md(res: dict) -> str:
    filas = []
    for nombre, m in res["modelos"].items():
        ic = m.get("pr_auc_ic95")
        ic_txt = f" [{ic[0]:.3f}–{ic[1]:.3f}]" if ic else ""
        clave_recall = [k for k in m if k.startswith("recall_a_precision")][0]
        filas.append(f"| {nombre} | {m['pr_auc']:.3f}{ic_txt} | {m['roc_auc']:.3f} | {m['brier']:.4f} | {m[clave_recall]:.3f} |")
    aviso = ""
    if res["completitud_detalle"] < 0.98:
        aviso = (f"\n> **Preliminar:** el detalle cubre el {res['completitud_detalle']:.0%} de las licitaciones resueltas; "
                 "la cohorte aún está sesgada hacia resultados rápidos. Se re-entrena al completar la descarga.\n")
    imp = "\n".join(f"| {n} | {g:.1%} |" for n, g in res["importancias_lightgbm"])
    return f"""# Resultados del modelo: ¿quedará desierta la licitación?
{aviso}
Generado: {res['generado']} · Cohorte: publicadas {res['periodos']['train'][0]} → {res['periodos']['test'][1]}

| Partición | n | Período de publicación | % desiertas |
|---|---|---|---|
| Entrenamiento | {res['n']['train']} | {res['periodos']['train'][0]} → {res['periodos']['train'][1]} | {res['tasa_desierta']['train']:.1%} |
| Validación | {res['n']['valid']} | {res['periodos']['valid'][0]} → {res['periodos']['valid'][1]} | {res['tasa_desierta']['valid']:.1%} |
| Prueba | {res['n']['test']} | {res['periodos']['test'][0]} → {res['periodos']['test'][1]} | {res['tasa_desierta']['test']:.1%} |

## Métricas en prueba

| Modelo | PR-AUC [IC 95%] | ROC-AUC | Brier | Recall a precisión {PRECISION_OBJETIVO:.0%} |
|---|---|---|---|---|
{chr(10).join(filas)}

## Variables más importantes (LightGBM, ganancia)

| Variable | Ganancia |
|---|---|
{imp}

*Fuente de los datos: Dirección ChileCompra.*
"""


def registrar_mlflow(res: dict, raiz: Path) -> None:
    try:
        import mlflow
    except ImportError:
        return
    mlflow.set_tracking_uri(f"sqlite:///{(raiz / 'data' / 'mlflow.db').resolve()}")
    mlflow.set_experiment("licitacion-desierta")
    with mlflow.start_run(run_name=f"lightgbm-{res['generado']}"):
        mlflow.log_params({"n_train": res["n"]["train"], "n_test": res["n"]["test"],
                           "completitud_detalle": round(res["completitud_detalle"], 4),
                           "lightgbm_iteraciones": res["lightgbm_iteraciones"]})
        for modelo, m in res["modelos"].items():
            for k, v in m.items():
                if isinstance(v, float):
                    mlflow.log_metric(f"{modelo}.{k}", v)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    p.add_argument("--salida", type=Path, default=Path("reports"))
    a = p.parse_args(argv)

    df = cargar(a.db)
    res = evaluar(df)
    res["completitud_detalle"] = completitud_detalle(a.db)
    modelo = res.pop("_modelo_lightgbm")

    a.salida.mkdir(parents=True, exist_ok=True)
    (a.salida / "modelo_resultados.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (a.salida / "modelo_resultados.md").write_text(reporte_md(res), encoding="utf-8")
    Path("models").mkdir(exist_ok=True)
    modelo.booster_.save_model("models/lightgbm_desierta.txt")
    registrar_mlflow(res, Path.cwd())
    print(reporte_md(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
