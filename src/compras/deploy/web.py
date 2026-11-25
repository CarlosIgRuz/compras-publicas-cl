"""Exporta el modelo para el navegador: `modelo.json` que lee `static/modelo.js` (P1.10).

Incluye los árboles de LightGBM en un formato compacto, las categorías conocidas, el suavizado
del historial, los umbrales de riesgo y los historiales por organismo y rubro.

Uso: python -m compras.deploy.web [--modelo artifacts/modelo] [--salida build/web/modelo.json]
Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from compras.api.app import ETIQUETAS


def _nodo(n: dict, categoricas_idx: set[int]) -> dict:
    if "leaf_value" in n:
        return {"hoja": round(n["leaf_value"], 10)}
    out = {"f": n["split_feature"], "interno": round(n["internal_value"], 10),
           "izq": _nodo(n["left_child"], categoricas_idx), "der": _nodo(n["right_child"], categoricas_idx)}
    if n["decision_type"] == "==":
        out["cat"] = [int(c) for c in str(n["threshold"]).split("||")]
    else:
        out.update(umbral=n["threshold"], faltante=n.get("missing_type", "None"),
                   izq_por_defecto=bool(n.get("default_left", True)))
    return out


def exportar_web(modelo: Path) -> dict:
    import lightgbm as lgb

    meta = json.loads((modelo / "metadata.json").read_text(encoding="utf-8"))
    dump = lgb.Booster(model_file=str(modelo / "lightgbm.txt")).dump_model()
    variables = dump["feature_names"]
    categoricas = meta["categoricas"]
    # códigos de categoría = posición en la lista que guardó LightGBM al entrenar (pandas_categorical)
    categorias = {c: lista for c, lista in zip(categoricas, dump["pandas_categorical"])}
    assert all(categorias[c] == meta["categorias"][c] for c in categoricas), "categorías desalineadas"
    idx_cat = {variables.index(c) for c in categoricas}
    org = json.loads((modelo / "historial_organismos.json").read_text(encoding="utf-8"))
    rub = json.loads((modelo / "historial_rubros.json").read_text(encoding="utf-8"))
    return {
        "version": meta["version"], "variables": variables, "categorias": categorias,
        "etiquetas": ETIQUETAS, "suavizado": meta["suavizado"], "umbrales": meta["umbrales"],
        "tasa_base": meta["tasa_base"], "metricas_prueba": meta["metricas_prueba"], "datos": meta["datos"],
        "historial_organismos": org, "historial_rubros": rub,
        "arboles": [_nodo(t["tree_structure"], idx_cat) for t in dump["tree_info"]],
        "fuente": "Dirección ChileCompra",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--modelo", type=Path, default=Path("artifacts/modelo"))
    p.add_argument("--salida", type=Path, default=Path("build/web/modelo.json"))
    a = p.parse_args(argv)
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(exportar_web(a.modelo), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{a.salida} ({a.salida.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
