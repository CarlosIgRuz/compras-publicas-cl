"""Descarga del detalle por licitación (montos, organismo, rubro, oferentes).

Fuente: listados diarios ya guardados en data/raw/licitaciones/.
Destino: data/raw/detalle/fecha=YYYY-MM-DD.json.gz — una lista de registros
{"codigo", "descargado", "detalle"} por día de publicación.

Reglas (ver DECISIONS.md):
- Solo días "maduros" (publicados hace >= MADUREZ_DIAS): así el detalle refleja el estado final
  (adjudicada / desierta / revocada) y no una foto de una licitación aún abierta.
- Nunca repite descargas: un código ya guardado en cualquier día se omite; el avance se guarda en
  un checkpoint `fecha=YYYY-MM-DD.parcial.jsonl` y la corrida siguiente continúa desde ahí.
- Tope interno de requests (bajo el límite de 10.000/día) y tope de minutos.
- Fuera del horario 22:00–07:00 (Chile) el tope se reduce a FUERA_DE_HORARIO_MAX (pruebas pequeñas).

Uso: python -m compras.ingest.detalle --tope 9000 --max-minutos 240
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .client import MercadoPublicoClient

LISTADOS_DIR = Path("data/raw/licitaciones")
DETALLE_DIR = Path("data/raw/detalle")
MADUREZ_DIAS = 60
TOPE_REQUESTS = 9000
FUERA_DE_HORARIO_MAX = 100
TZ_CHILE = ZoneInfo("America/Santiago")


def fecha_de_archivo(p: Path) -> date:
    return date.fromisoformat(p.name.split("=")[1][:10])


def ruta_final(d: date, detalle_dir: Path) -> Path:
    return detalle_dir / f"fecha={d.isoformat()}.json.gz"


def ruta_parcial(d: date, detalle_dir: Path) -> Path:
    return detalle_dir / f"fecha={d.isoformat()}.parcial.jsonl"


def dias_pendientes(hoy: date, listados_dir: Path, detalle_dir: Path, madurez: int = MADUREZ_DIAS) -> list[date]:
    """Días con listado, suficientemente antiguos y sin archivo final de detalle (más antiguos primero)."""
    limite = hoy - timedelta(days=madurez)
    dias = (fecha_de_archivo(p) for p in listados_dir.glob("fecha=*.json.gz"))
    return sorted(d for d in dias if d <= limite and not ruta_final(d, detalle_dir).exists())


def codigos_del_dia(d: date, listados_dir: Path) -> list[str]:
    with gzip.open(listados_dir / f"fecha={d.isoformat()}.json.gz", "rt", encoding="utf-8") as f:
        listado = json.load(f)
    return list(dict.fromkeys(x["CodigoExterno"] for x in listado))  # únicos, en orden


def codigos_guardados(detalle_dir: Path) -> set[str]:
    """Códigos ya presentes en archivos finales (para no repetir licitaciones listadas en dos días)."""
    vistos: set[str] = set()
    for p in detalle_dir.glob("fecha=*.json.gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            vistos.update(r["codigo"] for r in json.load(f))
    return vistos


def leer_parcial(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(linea) for linea in p.read_text(encoding="utf-8").splitlines() if linea.strip()]


def en_horario_nocturno(ahora: datetime) -> bool:
    h = ahora.astimezone(TZ_CHILE).hour
    return h >= 22 or h < 7


@dataclass
class Resumen:
    dias_completos: list[date] = field(default_factory=list)
    descargados: int = 0
    requests: int = 0
    motivo_fin: str = "sin pendientes"
    error: str | None = None


def extraer_detalle(
    client: MercadoPublicoClient,
    hoy: date | None = None,
    ahora: datetime | None = None,
    tope: int = TOPE_REQUESTS,
    max_minutos: float = 240,
    madurez: int = MADUREZ_DIAS,
    listados_dir: Path = LISTADOS_DIR,
    detalle_dir: Path = DETALLE_DIR,
) -> Resumen:
    ahora = ahora or datetime.now(TZ_CHILE)
    hoy = hoy or ahora.astimezone(TZ_CHILE).date()
    if not en_horario_nocturno(ahora):
        tope = min(tope, FUERA_DE_HORARIO_MAX)
        print(f"Fuera del horario 22:00–07:00: tope reducido a {tope} requests")
    detalle_dir.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    base = client.requests_hechos
    res = Resumen()
    guardados = codigos_guardados(detalle_dir)

    for d in dias_pendientes(hoy, listados_dir, detalle_dir, madurez):
        parcial = ruta_parcial(d, detalle_dir)
        hechos = {r["codigo"] for r in leer_parcial(parcial)}
        faltan = [c for c in codigos_del_dia(d, listados_dir) if c not in hechos and c not in guardados]

        cortado = False
        with parcial.open("a", encoding="utf-8") as out:
            for codigo in faltan:
                # margen de 3: un código puede consumir hasta 3 requests con reintentos
                if client.requests_hechos - base + 3 > tope:
                    res.motivo_fin, cortado = "tope de requests", True
                    break
                if (time.monotonic() - inicio) / 60 >= max_minutos:
                    res.motivo_fin, cortado = "tope de minutos", True
                    break
                try:
                    det = client.licitacion(codigo)
                except ConnectionError as e:
                    res.motivo_fin, res.error, cortado = "error de API", str(e), True
                    break
                registro = {"codigo": codigo, "descargado": datetime.now(TZ_CHILE).isoformat(timespec="seconds"), "detalle": det}
                out.write(json.dumps(registro, ensure_ascii=False) + "\n")
                out.flush()
                res.descargados += 1
        if cortado:  # se cortó a mitad del día: el checkpoint queda para la próxima corrida
            break

        registros = leer_parcial(parcial)
        with gzip.open(ruta_final(d, detalle_dir), "wt", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False)
        parcial.unlink()
        guardados.update(r["codigo"] for r in registros)
        res.dias_completos.append(d)
        print(f"{d}: {len(registros)} detalles")

    res.requests = client.requests_hechos - base
    return res


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tope", type=int, default=TOPE_REQUESTS, help="máximo de requests en esta corrida")
    p.add_argument("--max-minutos", type=float, default=240)
    p.add_argument("--madurez", type=int, default=MADUREZ_DIAS, help="días mínimos desde la publicación")
    a = p.parse_args(argv)
    res = extraer_detalle(MercadoPublicoClient(), tope=a.tope, max_minutos=a.max_minutos, madurez=a.madurez)
    print(
        f"Días completos: {len(res.dias_completos)} · detalles nuevos: {res.descargados} · "
        f"requests: {res.requests} · fin: {res.motivo_fin}"
    )
    if res.error:
        print(f"ERROR: {res.error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
