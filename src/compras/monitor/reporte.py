"""Reporte de monitoreo del modelo (P1.9).

Tres preguntas, con reglas explícitas para decidir si reentrenar (ver DECISIONS.md):
1. ¿Cambiaron los datos? PSI de cada variable entre la cohorte de entrenamiento y las licitaciones
   publicadas en los últimos 28 días.
2. ¿Cambió lo que predice el modelo? Probabilidad media predicha frente a la tasa base.
3. ¿Sigue acertando? Se cruzan las predicciones guardadas al publicar con el resultado real.
   Las licitaciones que se resuelven primero tienden a ser desiertas (mismo sesgo que en el
   entrenamiento), así que solo las publicadas hace ≥ HORIZONTE_DIAS dan una evaluación
   definitiva; las más nuevas se muestran como provisionales y no activan alertas.

Uso: python -m compras.monitor.reporte [--db data/warehouse.duckdb] [--salida reports]
Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONTE_DIAS = 120
VENTANA_DIAS = 28
PSI_VIGILAR, PSI_ALERTA = 0.10, 0.25
MIN_DEFINITIVAS_CALIBRACION, BRECHA_CALIBRACION = 300, 0.05
MIN_DEFINITIVAS_AUC, AUC_MINIMO = 500, 0.589  # ROC-AUC del baseline tipo × rubro en la prueba
EDAD_MAXIMA_DIAS = 90
NUMERICAS = ["n_items", "n_rubros", "log_monto", "hora_publicacion"]
CATEGORICAS = ["tipo", "rubro_principal", "region", "moneda", "convocatoria", "dia_semana_publicacion", "monto_desconocido"]


def variables_monitoreo(df: pd.DataFrame) -> pd.DataFrame:
    """Mismas variables para la referencia (entrenamiento) y la población actual (publicadas)."""
    fecha = pd.to_datetime(df["fecha_publicacion"])
    monto = pd.to_numeric(df["monto_estimado_clp"], errors="coerce")
    out = pd.DataFrame({
        "n_items": pd.to_numeric(df["n_items"], errors="coerce"),
        "n_rubros": pd.to_numeric(df["n_rubros"], errors="coerce"),
        "log_monto": np.log1p(monto),
        "hora_publicacion": fecha.dt.hour,
        "dia_semana_publicacion": fecha.dt.dayofweek.astype(str),
        "monto_desconocido": monto.isna().astype(str),
    })
    for c in ("tipo", "rubro_principal", "region", "moneda", "convocatoria"):
        out[c] = df[c].fillna("desconocido").astype(str)
    return out


def psi(ref: pd.Series, act: pd.Series, numerica: bool, bins: int = 10, max_cat: int = 15) -> float:
    """Population Stability Index. Numéricas: deciles de la referencia (+ faltantes aparte).
    Categóricas: las `max_cat` más frecuentes en la referencia y el resto como "otros"."""
    eps = 1e-4
    if numerica:
        r, a = ref.astype(float), act.astype(float)
        cortes = np.unique(np.nanquantile(r.dropna(), np.linspace(0, 1, bins + 1)))
        cortes[0], cortes[-1] = -np.inf, np.inf

        def dist(x):
            cuenta = pd.cut(x.dropna(), cortes, include_lowest=True).value_counts(sort=False).to_numpy().astype(float)
            return np.append(cuenta, x.isna().sum())
        pr, pa = dist(r), dist(a)
    else:
        top = ref.value_counts().index[:max_cat]
        r = ref.where(ref.isin(top), "otros")
        a = act.where(act.isin(top), "otros")
        cats = sorted(set(r) | set(a))
        pr = r.value_counts().reindex(cats, fill_value=0).to_numpy().astype(float)
        pa = a.value_counts().reindex(cats, fill_value=0).to_numpy().astype(float)
    pr = pr / max(pr.sum(), 1) + eps
    pa = pa / max(pa.sum(), 1) + eps
    return float(np.sum((pa - pr) * np.log(pa / pr)))


def calcular_drift(ref: pd.DataFrame, act: pd.DataFrame) -> dict[str, float]:
    vr, va = variables_monitoreo(ref), variables_monitoreo(act)
    return {c: round(psi(vr[c], va[c], numerica=c in NUMERICAS), 4) for c in NUMERICAS + CATEGORICAS}


def desempeno(pred: pd.DataFrame, resultados: pd.DataFrame, hoy: date) -> dict:
    """Cruza predicciones con resultados reales; separa definitivas (≥ HORIZONTE_DIAS) y provisionales."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    if pred.empty:
        return {"predicciones": 0, "resueltas": 0, "definitivas": {"n": 0}, "provisionales": {"n": 0}}
    unido = pred.merge(resultados[["codigo", "es_desierta"]], on="codigo", how="inner")
    # las fechas vienen con y sin milisegundos: ISO8601 acepta ambas
    edad = (pd.Timestamp(hoy) - pd.to_datetime(unido["fecha_publicacion"], format="ISO8601").dt.tz_localize(None)).dt.days
    salida = {"predicciones": int(len(pred)), "resueltas": int(len(unido))}
    for nombre, grupo in (("definitivas", unido[edad >= HORIZONTE_DIAS]), ("provisionales", unido[edad < HORIZONTE_DIAS])):
        y, p = grupo["es_desierta"].astype(int).to_numpy(), grupo["probabilidad"].to_numpy()
        m = {"n": int(len(grupo))}
        if len(grupo):
            m.update(tasa_observada=round(float(y.mean()), 4), probabilidad_media=round(float(p.mean()), 4))
        if len(grupo) >= 50 and 0 < y.mean() < 1:
            m.update(roc_auc=round(float(roc_auc_score(y, p)), 4), pr_auc=round(float(average_precision_score(y, p)), 4))
        salida[nombre] = m
    return salida


def recomendacion(drift: dict[str, float], perf: dict, edad_modelo: int) -> dict:
    motivos = []
    fuertes = [f"{v} (PSI {x:.2f})" for v, x in drift.items() if x > PSI_ALERTA]
    if fuertes:
        motivos.append("cambio fuerte en los datos: " + ", ".join(fuertes))
    d = perf.get("definitivas", {})
    if d.get("n", 0) >= MIN_DEFINITIVAS_CALIBRACION:
        brecha = d["probabilidad_media"] - d["tasa_observada"]
        if abs(brecha) > BRECHA_CALIBRACION:
            motivos.append(f"descalibración: predice {d['probabilidad_media']:.1%} y se observa {d['tasa_observada']:.1%}")
    if d.get("n", 0) >= MIN_DEFINITIVAS_AUC and d.get("roc_auc", 1) < AUC_MINIMO:
        motivos.append(f"ROC-AUC {d['roc_auc']:.3f} bajo el baseline tipo × rubro ({AUC_MINIMO})")
    if edad_modelo > EDAD_MAXIMA_DIAS:
        motivos.append(f"el modelo tiene {edad_modelo} días (máximo {EDAD_MAXIMA_DIAS})")
    vigilar = [v for v, x in drift.items() if PSI_VIGILAR < x <= PSI_ALERTA]
    return {"reentrenar": bool(motivos), "motivos": motivos, "vigilar": vigilar}


def reporte_md(r: dict) -> str:
    def nivel(x):
        return "🔴 alerta" if x > PSI_ALERTA else "🟡 vigilar" if x > PSI_VIGILAR else "🟢 estable"
    filas_drift = "\n".join(f"| {v} | {x:.3f} | {nivel(x)} |" for v, x in sorted(r["drift"].items(), key=lambda kv: -kv[1]))
    p = r["desempeno"]

    def fila_perf(nombre, etiqueta):
        m = p.get(nombre, {})
        if not m.get("n"):
            return f"| {etiqueta} | 0 | – | – | – |"
        auc = f"{m['roc_auc']:.3f}" if "roc_auc" in m else "– (n < 50)"
        return f"| {etiqueta} | {m['n']} | {m['probabilidad_media']:.1%} | {m['tasa_observada']:.1%} | {auc} |"
    rec = r["recomendacion"]
    decision = ("**Reentrenar.** " + "; ".join(rec["motivos"])) if rec["reentrenar"] else "**No es necesario reentrenar.**"
    vig = f" Vigilar: {', '.join(rec['vigilar'])}." if rec["vigilar"] else ""
    return f"""# Monitoreo del modelo de licitaciones desiertas

Generado: {r['generado']} · Modelo: {r['modelo']['version']} ({r['modelo']['edad_dias']} días)

{decision}{vig}

## 1. ¿Cambiaron los datos?
Licitaciones publicadas en los últimos {VENTANA_DIAS} días ({r['ventana']['desde']} → {r['ventana']['hasta']}, n = {r['ventana']['n']}) frente a la cohorte de entrenamiento (n = {r['referencia_n']}). PSI: < {PSI_VIGILAR} estable, {PSI_VIGILAR}–{PSI_ALERTA} vigilar, > {PSI_ALERTA} alerta.

| Variable | PSI | Estado |
|---|---|---|
{filas_drift}

## 2. ¿Cambió lo que predice el modelo?
Probabilidad media predicha en la ventana: **{r['prediccion_media']:.1%}** (tasa base del entrenamiento: {r['modelo']['tasa_base']:.1%}). Nivel alto: {r['niveles'].get('alto', 0):.1%} de las licitaciones (esperado ≈ 10%).

## 3. ¿Sigue acertando?
{p['predicciones']} predicciones guardadas; {p['resueltas']} ya resueltas. Solo las publicadas hace ≥ {HORIZONTE_DIAS} días son una evaluación definitiva (las que se resuelven antes están sesgadas hacia desiertas).

| Evaluación | n | Probabilidad media predicha | Tasa observada | ROC-AUC |
|---|---|---|---|---|
{fila_perf('definitivas', f'Definitiva (≥ {HORIZONTE_DIAS} días)')}
{fila_perf('provisionales', 'Provisional (sesgada)')}

## Reglas de reentrenamiento
Reentrenar si ocurre cualquiera de estas condiciones: alguna variable con PSI > {PSI_ALERTA}; con ≥ {MIN_DEFINITIVAS_CALIBRACION} evaluaciones definitivas, diferencia entre lo predicho y lo observado > {BRECHA_CALIBRACION:.0%}; con ≥ {MIN_DEFINITIVAS_AUC} definitivas, ROC-AUC < {AUC_MINIMO} (el baseline tipo × rubro); o un modelo de más de {EDAD_MAXIMA_DIAS} días.

*Fuente de los datos: Dirección ChileCompra.*
"""


def main(argv: list[str] | None = None) -> int:
    import duckdb

    from compras.monitor.puntuar import PREDICCIONES

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    ap.add_argument("--modelo", type=Path, default=Path("artifacts/modelo"))
    ap.add_argument("--salida", type=Path, default=Path("reports"))
    a = ap.parse_args(argv)

    con = duckdb.connect(str(a.db), read_only=True)
    cols = "codigo, fecha_publicacion, tipo, convocatoria, rubro_principal, n_items, n_rubros, moneda, region, monto_estimado_clp"
    ref = con.execute(f"""select {cols} from fct_licitaciones
                          where codigo in (select codigo from ml_licitaciones where en_cohorte and es_desierta is not null)""").df()
    act = con.execute(f"select {cols} from ml_publicadas").df()
    resultados = con.execute("select codigo, es_desierta from fct_licitaciones where tiene_resultado").df()
    con.close()

    meta = json.loads((a.modelo / "metadata.json").read_text(encoding="utf-8"))
    hoy = date.today()
    if len(act):
        hasta = pd.to_datetime(act["fecha_publicacion"]).max()
        act = act[pd.to_datetime(act["fecha_publicacion"]) > hasta - pd.Timedelta(days=VENTANA_DIAS)]
    pred = pd.read_json(PREDICCIONES, lines=True, dtype={"codigo": str}, convert_dates=False) if PREDICCIONES.exists() else pd.DataFrame(
        columns=["codigo", "fecha_publicacion", "probabilidad", "nivel"])
    pred_ventana = pred[pred["codigo"].isin(act["codigo"])] if len(pred) else pred

    drift = calcular_drift(ref, act) if len(act) >= 100 else {}
    perf = desempeno(pred, resultados, hoy)
    edad = (hoy - date.fromisoformat(meta["version"])).days
    r = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "modelo": {"version": meta["version"], "edad_dias": edad, "tasa_base": meta["tasa_base"]},
        "referencia_n": int(len(ref)),
        "ventana": {"n": int(len(act)),
                    "desde": str(pd.to_datetime(act["fecha_publicacion"]).min().date()) if len(act) else None,
                    "hasta": str(pd.to_datetime(act["fecha_publicacion"]).max().date()) if len(act) else None},
        "drift": drift,
        "prediccion_media": float(pred_ventana["probabilidad"].mean()) if len(pred_ventana) else float("nan"),
        "niveles": pred_ventana["nivel"].value_counts(normalize=True).to_dict() if len(pred_ventana) else {},
        "desempeno": perf,
        "recomendacion": recomendacion(drift, perf, edad),
    }
    a.salida.mkdir(parents=True, exist_ok=True)
    (a.salida / "monitoreo.json").write_text(json.dumps(r, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if len(act) < 100:
        texto = (f"# Monitoreo del modelo de licitaciones desiertas\n\nGenerado: {r['generado']}\n\n"
                 f"Aún no hay suficientes licitaciones recién publicadas con detalle ({len(act)}; se necesitan 100). "
                 "El primer reporte sale después de la primera descarga nocturna.\n\n*Fuente de los datos: Dirección ChileCompra.*\n")
    else:
        texto = reporte_md(r)
    (a.salida / "monitoreo.md").write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
