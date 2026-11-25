"""Ranking de oportunidades: dónde hay más riesgo de licitaciones desiertas ahora.

Para proveedores: una licitación con alto riesgo de quedar desierta suele tener poca competencia,
o bases difíciles de cumplir (en el 69% de las desiertas hubo ofertas, pero se rechazaron).
Se actualiza cada día con las predicciones que guarda el monitoreo (`compras.monitor.puntuar`).

Salida: `reports/oportunidades.json`, que lee la página de demo.
- `rubros`: rubros de las licitaciones publicadas en los últimos VENTANA_DIAS días, ordenados por
  probabilidad media predicha, con su historial de desiertas y la mediana de oferentes.
- `abiertas`: licitaciones con cierre futuro y mayor probabilidad de quedar desiertas.

Uso: python -m compras.monitor.oportunidades [--db data/warehouse.duckdb]
Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

VENTANA_DIAS = 28
MIN_PUBLICADAS = 30
TOP_RUBROS, TOP_ABIERTAS = 10, 12
TZ_CHILE = ZoneInfo("America/Santiago")
URL_FICHA = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={}"


def ranking_rubros(pub: pd.DataFrame, historial: pd.DataFrame, hasta: pd.Timestamp) -> list[dict]:
    """`pub`: publicadas con su probabilidad predicha; `historial`: dim_rubros."""
    recientes = pub[pd.to_datetime(pub["fecha_publicacion"]) > hasta - pd.Timedelta(days=VENTANA_DIAS)]
    g = (recientes.dropna(subset=["rubro_principal"]).groupby("rubro_principal")
         .agg(publicadas=("codigo", "count"), probabilidad_media=("probabilidad", "mean"),
              pct_alto=("nivel", lambda s: (s == "alto").mean())))
    g = g[g["publicadas"] >= MIN_PUBLICADAS].join(
        historial.set_index("rubro")[["tasa_desierta", "oferentes_mediana"]], how="left")
    g = g.sort_values("probabilidad_media", ascending=False).head(TOP_RUBROS)
    return [{"rubro": r, "publicadas": int(f.publicadas), "probabilidad_media": round(float(f.probabilidad_media), 4),
             "pct_alto": round(float(f.pct_alto), 4),
             "tasa_desierta_historica": None if pd.isna(f.tasa_desierta) else round(float(f.tasa_desierta), 4),
             "oferentes_mediana": None if pd.isna(f.oferentes_mediana) else float(f.oferentes_mediana)}
            for r, f in g.iterrows()]


def abiertas_riesgosas(pub: pd.DataFrame, ahora: datetime) -> list[dict]:
    cierre = pd.to_datetime(pub["fecha_cierre"])
    abiertas = pub[cierre > pd.Timestamp(ahora.replace(tzinfo=None))]
    top = abiertas.sort_values(["probabilidad", "codigo"], ascending=[False, True]).head(TOP_ABIERTAS)
    return [{"codigo": f.codigo, "nombre": f.nombre, "organismo": f.organismo, "rubro": f.rubro_principal,
             "probabilidad": round(float(f.probabilidad), 4), "nivel": f.nivel,
             "cierre": pd.Timestamp(f.fecha_cierre).strftime("%Y-%m-%d %H:%M"), "url": URL_FICHA.format(f.codigo)}
            for f in top.itertuples()]


def main(argv: list[str] | None = None) -> int:
    import duckdb

    from compras.monitor.puntuar import PREDICCIONES

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    ap.add_argument("--salida", type=Path, default=Path("reports/oportunidades.json"))
    a = ap.parse_args(argv)

    con = duckdb.connect(str(a.db), read_only=True)
    pub = con.execute("select codigo, nombre, organismo, rubro_principal, fecha_publicacion, fecha_cierre from ml_publicadas").df()
    historial = con.execute("select rubro, tasa_desierta, oferentes_mediana from dim_rubros").df()
    con.close()
    pred = pd.read_json(PREDICCIONES, lines=True, dtype={"codigo": str}, convert_dates=False)[["codigo", "probabilidad", "nivel"]]
    pub = pub.merge(pred.drop_duplicates("codigo", keep="last"), on="codigo", how="inner")

    ahora = datetime.now(TZ_CHILE)
    hasta = pd.to_datetime(pub["fecha_publicacion"]).max()
    salida = {
        "generado": ahora.isoformat(timespec="minutes"),
        "ventana": {"dias": VENTANA_DIAS, "hasta": str(hasta.date())},
        "rubros": ranking_rubros(pub, historial, hasta),
        "abiertas": abiertas_riesgosas(pub, ahora),
        "fuente": "Dirección ChileCompra",
    }
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(salida['rubros'])} rubros · {len(salida['abiertas'])} licitaciones abiertas → {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
