"""Puntuación diaria: aplica el modelo desplegado a las licitaciones recién publicadas (P1.9).

Lee `ml_publicadas` del warehouse, puntúa las que aún no tienen predicción con el mismo código que
usa la API (`compras.api.app.Modelo`) y agrega las predicciones a `data/predicciones/predicciones.jsonl`
(versionado). Así queda un registro de lo que el modelo dijo al publicar, para compararlo con lo que
pasó cuando la licitación se resuelva.

Uso: python -m compras.monitor.puntuar [--db data/warehouse.duckdb]
Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from compras.api.app import Licitacion, Modelo

PREDICCIONES = Path("data/predicciones/predicciones.jsonl")
TZ_CHILE = ZoneInfo("America/Santiago")


def _limpio(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT else v


def a_licitacion(fila: dict) -> Licitacion:
    n_items = max(1, int(_limpio(fila.get("n_items")) or 1))
    n_rubros = min(n_items, max(1, int(_limpio(fila.get("n_rubros")) or 1)))
    conv = _limpio(fila.get("convocatoria"))
    etapas = _limpio(fila.get("etapas"))
    visible = _limpio(fila.get("monto_visible"))
    fecha = _limpio(fila.get("fecha_publicacion"))
    return Licitacion(
        tipo=_limpio(fila.get("tipo")) or "desconocido",
        rubro_principal=_limpio(fila.get("rubro_principal")),
        n_items=n_items, n_rubros=n_rubros,
        convocatoria=conv if conv in ("publica", "privada") else None,
        moneda=_limpio(fila.get("moneda")) or "desconocido",
        region=_limpio(fila.get("region")),
        codigo_organismo=_limpio(fila.get("codigo_organismo")),
        etapas=int(etapas) if etapas in (1, 2) else None,
        monto_estimado_clp=_limpio(fila.get("monto_estimado_clp")),
        monto_visible=None if visible is None else bool(visible),
        fecha_publicacion=pd.Timestamp(fecha).to_pydatetime() if fecha is not None else None,
    )


def ya_puntuadas(ruta: Path = PREDICCIONES) -> set[str]:
    if not ruta.exists():
        return set()
    return {json.loads(l)["codigo"] for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()}


def puntuar(df: pd.DataFrame, modelo: Modelo, excluir: set[str]) -> list[dict]:
    ahora = datetime.now(TZ_CHILE).isoformat(timespec="seconds")
    filas = []
    for fila in df.to_dict("records"):
        if fila["codigo"] in excluir:
            continue
        pred = modelo.predecir(a_licitacion(fila))
        filas.append({
            "codigo": fila["codigo"],
            "fecha_publicacion": str(pd.Timestamp(fila["fecha_publicacion"])),
            "probabilidad": pred.probabilidad_desierta,
            "nivel": pred.nivel,
            "modelo": pred.modelo["version"],
            "puntuado": ahora,
        })
    return filas


def main(argv: list[str] | None = None) -> int:
    import duckdb

    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    p.add_argument("--modelo", type=Path, default=Path("artifacts/modelo"))
    a = p.parse_args(argv)
    con = duckdb.connect(str(a.db), read_only=True)
    df = con.execute("select * from ml_publicadas order by fecha_publicacion, codigo").df()
    con.close()
    nuevas = puntuar(df, Modelo(a.modelo), ya_puntuadas(PREDICCIONES))
    PREDICCIONES.parent.mkdir(parents=True, exist_ok=True)
    with PREDICCIONES.open("a", encoding="utf-8") as f:
        for fila in nuevas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    print(f"Publicadas en el warehouse: {len(df)} · puntuadas ahora: {len(nuevas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
