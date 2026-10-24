"""API de predicción: riesgo de que una licitación quede desierta (P1.8).

Recibe los datos que se conocen al publicar una licitación y devuelve la probabilidad de que
quede desierta, un nivel de riesgo y los factores que más pesaron (contribuciones SHAP de LightGBM).
El historial del organismo y del rubro se toma de los artefactos exportados por el entrenamiento.

Uso local:  MODELO_DIR=artifacts/modelo uvicorn compras.api.app:app --app-dir src
Fuente de los datos: Dirección ChileCompra.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import lightgbm as lgb
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

TZ_CHILE = ZoneInfo("America/Santiago")
ETIQUETAS = {
    "tipo": "tipo de licitación", "convocatoria": "convocatoria", "rubro_principal": "rubro",
    "moneda": "moneda", "region": "región", "etapas": "n° de etapas",
    "dia_semana_publicacion": "día de publicación", "hora_publicacion": "hora de publicación",
    "n_items": "n° de ítems", "n_rubros": "n° de rubros", "monto_visible": "monto visible",
    "monto_desconocido": "monto no informado", "log_monto_estimado_clp": "monto estimado",
    "org_n_previas": "experiencia del organismo", "org_tasa_desierta_previa": "historial de desiertas del organismo",
    "rubro_n_previas": "volumen del rubro", "rubro_tasa_desierta_previa": "historial de desiertas del rubro",
}


class Licitacion(BaseModel):
    """Datos conocidos al momento de publicar."""
    tipo: str = Field(examples=["LE"], description="Tipo según el código (L1, LE, LP, LR, CO, ...)")
    rubro_principal: str | None = Field(None, examples=["Equipamiento y suministros médicos"])
    n_items: int = Field(ge=1, examples=[3])
    n_rubros: int = Field(1, ge=1)
    convocatoria: Literal["publica", "privada"] | None = "publica"
    moneda: str = "CLP"
    region: str | None = Field(None, examples=["Región Metropolitana de Santiago"])
    codigo_organismo: str | None = Field(None, examples=["7479"])
    etapas: int | None = Field(None, ge=1, le=2)
    monto_estimado_clp: float | None = Field(None, ge=0, examples=[25_000_000])
    monto_visible: bool | None = None
    fecha_publicacion: datetime | None = Field(None, description="Por defecto, ahora (hora de Chile)")


class Factor(BaseModel):
    variable: str
    efecto: Literal["sube el riesgo", "baja el riesgo"]
    contribucion: float = Field(description="Aporte en log-odds (SHAP)")


class Prediccion(BaseModel):
    probabilidad_desierta: float
    nivel: Literal["alto", "medio", "bajo"]
    tasa_base: float
    factores: list[Factor]
    historial_organismo: dict
    modelo: dict
    fuente: str = "Dirección ChileCompra"


class Modelo:
    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.meta = json.loads((carpeta / "metadata.json").read_text(encoding="utf-8"))
        self.booster = lgb.Booster(model_file=str(carpeta / "lightgbm.txt"))
        self.hist_org = json.loads((carpeta / "historial_organismos.json").read_text(encoding="utf-8"))
        self.hist_rubro = json.loads((carpeta / "historial_rubros.json").read_text(encoding="utf-8"))
        self.columnas = self.meta["categoricas"] + self.meta["numericas"]

    def _tasa(self, h: dict | None) -> tuple[int, float]:
        m, p0 = self.meta["suavizado"]["m"], self.meta["suavizado"]["p0"]
        n, d = (h["n"], h["desiertas"]) if h else (0, 0)
        return n, (d + m * p0) / (n + m)

    def variables(self, lic: Licitacion) -> pd.DataFrame:
        """Construye las variables igual que `train.preparar` (lo verifica un test)."""
        fecha = (lic.fecha_publicacion or datetime.now(TZ_CHILE))
        org_n, org_tasa = self._tasa(self.hist_org.get(lic.codigo_organismo or ""))
        rub_n, rub_tasa = self._tasa(self.hist_rubro.get(lic.rubro_principal or ""))
        monto = lic.monto_estimado_clp if lic.moneda == "CLP" else None
        fila = {
            "tipo": lic.tipo, "convocatoria": lic.convocatoria, "rubro_principal": lic.rubro_principal,
            "moneda": lic.moneda, "region": lic.region,
            "etapas": lic.etapas, "dia_semana_publicacion": fecha.isoweekday(), "hora_publicacion": fecha.hour,
            "n_items": lic.n_items, "n_rubros": lic.n_rubros,
            "monto_visible": None if lic.monto_visible is None else float(lic.monto_visible),
            "monto_desconocido": float(monto is None),
            "log_monto_estimado_clp": None if monto is None else math.log1p(monto),
            "org_n_previas": org_n, "org_tasa_desierta_previa": org_tasa,
            "rubro_n_previas": rub_n, "rubro_tasa_desierta_previa": rub_tasa,
        }
        X = pd.DataFrame([fila])[self.columnas]
        for c in self.meta["categoricas"]:
            cats = self.meta["categorias"][c]
            valor = X[c].fillna("desconocido").astype(str)
            X[c] = pd.Categorical(valor.where(valor.isin(cats)), categories=cats)
        for c in self.meta["numericas"]:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
        return X

    def predecir(self, lic: Licitacion) -> Prediccion:
        X = self.variables(lic)
        p = float(self.booster.predict(X)[0])
        contrib = self.booster.predict(X, pred_contrib=True)[0][:-1]  # el último es el sesgo
        orden = np.argsort(-np.abs(contrib))[:3]
        factores = [
            Factor(variable=ETIQUETAS.get(self.columnas[i], self.columnas[i]),
                   efecto="sube el riesgo" if contrib[i] > 0 else "baja el riesgo",
                   contribucion=round(float(contrib[i]), 4))
            for i in orden if abs(contrib[i]) > 1e-6
        ]
        u = self.meta["umbrales"]
        nivel = "alto" if p >= u["alto"] else "medio" if p >= u["medio"] else "bajo"
        h = self.hist_org.get(lic.codigo_organismo or "")
        return Prediccion(
            probabilidad_desierta=round(p, 4), nivel=nivel, tasa_base=round(self.meta["tasa_base"], 4),
            factores=factores,
            historial_organismo={"conocido": h is not None, "nombre": h["nombre"] if h else None,
                                 "licitaciones_resueltas": int(X.org_n_previas[0]),
                                 "tasa_desierta_suavizada": round(float(X.org_tasa_desierta_previa[0]), 4)},
            modelo={"version": self.meta["version"], "cohorte": self.meta["datos"]["cohorte"]},
        )


@lru_cache(maxsize=1)
def modelo() -> Modelo:
    return Modelo(Path(os.environ.get("MODELO_DIR", "artifacts/modelo")))


app = FastAPI(
    title="Riesgo de licitación desierta",
    description="Predice, al publicar, si una licitación de Mercado Público quedará desierta. "
                "Fuente de los datos: Dirección ChileCompra.",
    version="1.0",
)


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/docs")


@app.get("/health")
def health():
    m = modelo()
    return {"estado": "ok", "modelo": m.meta["version"]}


@app.get("/modelo")
def info_modelo():
    m = modelo().meta
    return {k: m[k] for k in ("version", "objetivo", "tasa_base", "umbrales", "metricas_prueba", "datos", "fuente")}


@app.get("/opciones")
def opciones():
    """Valores conocidos por el modelo para las variables categóricas (útil para formularios)."""
    return modelo().meta["categorias"]


@app.post("/predecir", response_model=Prediccion)
def predecir(lic: Licitacion):
    if lic.n_rubros > lic.n_items:
        raise HTTPException(422, "n_rubros no puede ser mayor que n_items")
    return modelo().predecir(lic)
