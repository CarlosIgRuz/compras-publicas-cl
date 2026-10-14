"""Ingesta incremental: guarda el listado diario en data/raw/licitaciones/fecha=YYYY-MM-DD.json.

Uso: python -m compras.ingest.extract --desde 2026-09-01 --hasta 2026-09-07
Los días ya descargados se omiten (cuidar el cupo diario de la API).
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from .client import MercadoPublicoClient

RAW_DIR = Path("data/raw/licitaciones")


def rango(desde: date, hasta: date):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def ruta_dia(d: date, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"fecha={d.isoformat()}.json"


def extraer(desde: date, hasta: date, client: MercadoPublicoClient, raw_dir: Path = RAW_DIR) -> int:
    raw_dir.mkdir(parents=True, exist_ok=True)
    nuevos = 0
    for d in rango(desde, hasta):
        destino = ruta_dia(d, raw_dir)
        if destino.exists():
            continue
        listado = client.licitaciones_por_fecha(d)
        destino.write_text(json.dumps(listado, ensure_ascii=False), encoding="utf-8")
        nuevos += 1
        print(f"{d}: {len(listado)} licitaciones")
    print(f"Días nuevos: {nuevos} · requests usados: {client.requests_hechos}")
    return nuevos


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--desde", type=date.fromisoformat, required=True)
    p.add_argument("--hasta", type=date.fromisoformat, required=True)
    a = p.parse_args()
    extraer(a.desde, a.hasta, MercadoPublicoClient())
