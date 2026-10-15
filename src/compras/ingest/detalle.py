"""Descarga del detalle por licitación (montos, organismo, rubro, oferentes).

Fuente: listados diarios ya guardados en data/raw/licitaciones/.
Destino: data/raw/detalle/fecha=YYYY-MM-DD.json.gz — una lista de registros
{"codigo", "descargado", "detalle"} por día de publicación.

Reglas (ver DECISIONS.md):
- Solo días "maduros" (publicados hace >= MADUREZ_DIAS): así el detalle refleja el estado final
  (adjudicada / desierta / revocada) y no una foto de una licitación aún abierta.
- Nunca repite descargas: un código ya guardado en cualquier día se omite; el avance se guarda en
  un checkpoint `fecha=YYYY-MM-DD.parcial.jsonl` y la corrida siguiente continúa desde ahí.
- Cupo propio de CUPO_DIARIO requests por día calendario de Chile (bajo el límite de 10.000/día de la API),
  sumando lo ya usado ese día según la bitácora `data/logs/detalle_corridas.jsonl`: una corrida atrasada o
  repetida nunca pasa el límite. Además, tope de requests y de minutos por corrida.
- Una corrida que parte de noche se detiene sola a las 07:00 (Chile). Fuera del horario 22:00–07:00 el tope
  se reduce a FUERA_DE_HORARIO_MAX (pruebas pequeñas).

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
from typing import Callable
from zoneinfo import ZoneInfo

from .client import MercadoPublicoClient

LISTADOS_DIR = Path("data/raw/licitaciones")
BITACORA = Path("data/logs/detalle_corridas.jsonl")
DETALLE_DIR = Path("data/raw/detalle")
MADUREZ_DIAS = 60
TOPE_REQUESTS = 9000
MAX_INTENTOS_CODIGO = 2  # corridas distintas; luego el código se guarda como fallido y no se reintenta
MAX_FALLOS_SEGUIDOS = 5  # más que esto se interpreta como API caída y se detiene la corrida
CUPO_DIARIO = 9000  # la ingesta de listados usa ~1 request/día; el resto queda de margen
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


def codigos_resueltos(registros: list[dict]) -> set[str]:
    """Códigos con detalle descargado, o que ya fallaron MAX_INTENTOS_CODIGO veces (se abandonan)."""
    fallos: dict[str, int] = {}
    resueltos: set[str] = set()
    for r in registros:
        if r.get("error"):
            fallos[r["codigo"]] = fallos.get(r["codigo"], 0) + 1
        else:
            resueltos.add(r["codigo"])
    return resueltos | {c for c, n in fallos.items() if n >= MAX_INTENTOS_CODIGO}


def consolidar(registros: list[dict]) -> list[dict]:
    """Un registro por código: el exitoso si existe; si no, el último error (detalle = null)."""
    por_codigo: dict[str, dict] = {}
    for r in registros:
        previo = por_codigo.get(r["codigo"])
        if previo is None or previo.get("error") or not r.get("error"):  # un éxito nunca se pisa con un error
            por_codigo[r["codigo"]] = r
    return list(por_codigo.values())


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
    requests_por_dia: dict[str, int] = field(default_factory=dict)
    fallidos: int = 0


def usos_previos(bitacora: Path = BITACORA) -> dict[str, int]:
    """Requests ya usados por día calendario de Chile, según la bitácora de corridas."""
    usados: dict[str, int] = {}
    if bitacora.exists():
        for linea in bitacora.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                for dia, n in json.loads(linea).get("requests_por_dia", {}).items():
                    usados[dia] = usados.get(dia, 0) + n
    return usados


def extraer_detalle(
    client: MercadoPublicoClient,
    hoy: date | None = None,
    ahora: datetime | None = None,
    tope: int = TOPE_REQUESTS,
    max_minutos: float = 240,
    madurez: int = MADUREZ_DIAS,
    listados_dir: Path = LISTADOS_DIR,
    detalle_dir: Path = DETALLE_DIR,
    usados_por_dia: dict[str, int] | None = None,
    reloj: Callable[[], datetime] | None = None,
) -> Resumen:
    if reloj is None:
        reloj = (lambda: ahora) if ahora else (lambda: datetime.now(TZ_CHILE))
    ahora = ahora or reloj()
    hoy = hoy or ahora.astimezone(TZ_CHILE).date()
    usados = usados_por_dia or {}
    nocturna = en_horario_nocturno(ahora)
    if not nocturna:
        tope = min(tope, FUERA_DE_HORARIO_MAX)
        print(f"Fuera del horario 22:00–07:00: tope reducido a {tope} requests")
    detalle_dir.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    base = client.requests_hechos
    res = Resumen()
    guardados = codigos_guardados(detalle_dir)

    for d in dias_pendientes(hoy, listados_dir, detalle_dir, madurez):
        parcial = ruta_parcial(d, detalle_dir)
        codigos = [c for c in codigos_del_dia(d, listados_dir) if c not in guardados]
        hechos = codigos_resueltos(leer_parcial(parcial))
        faltan = [c for c in codigos if c not in hechos]

        cortado = False
        seguidos = 0
        with parcial.open("a", encoding="utf-8") as out:
            for codigo in faltan:
                # margen de 3: un código puede consumir hasta 3 requests con reintentos
                if client.requests_hechos - base + 3 > tope:
                    res.motivo_fin, cortado = "tope de requests", True
                    break
                if (time.monotonic() - inicio) / 60 >= max_minutos:
                    res.motivo_fin, cortado = "tope de minutos", True
                    break
                momento = reloj().astimezone(TZ_CHILE)
                if nocturna and not en_horario_nocturno(momento):
                    res.motivo_fin, cortado = "fin del horario nocturno", True
                    break
                dia = momento.date().isoformat()
                if usados.get(dia, 0) + res.requests_por_dia.get(dia, 0) + 3 > CUPO_DIARIO:
                    res.motivo_fin, cortado = "cupo diario", True
                    break
                antes = client.requests_hechos
                registro = {"codigo": codigo, "descargado": datetime.now(TZ_CHILE).isoformat(timespec="seconds")}
                try:
                    registro["detalle"] = client.licitacion(codigo)
                except ConnectionError as e:
                    # un código con error no detiene la corrida: se anota y se reintenta en otra corrida
                    registro.update(detalle=None, error=str(e))
                    res.fallidos += 1
                    seguidos += 1
                else:
                    res.descargados += 1
                    seguidos = 0
                finally:
                    res.requests_por_dia[dia] = res.requests_por_dia.get(dia, 0) + client.requests_hechos - antes
                out.write(json.dumps(registro, ensure_ascii=False) + "\n")
                out.flush()
                if seguidos >= MAX_FALLOS_SEGUIDOS:
                    res.motivo_fin, res.error, cortado = "API caída", registro["error"], True
                    break
        if cortado:  # se cortó a mitad del día: el checkpoint queda para la próxima corrida
            break

        registros = leer_parcial(parcial)
        if not set(codigos) <= codigos_resueltos(registros):
            print(f"{d}: quedan códigos con error; se reintentan en la próxima corrida")
            continue  # el día queda en checkpoint; se sigue con el siguiente
        registros = consolidar(registros)
        with gzip.open(ruta_final(d, detalle_dir), "wt", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False)
        parcial.unlink()
        guardados.update(r["codigo"] for r in registros)
        res.dias_completos.append(d)
        print(f"{d}: {len(registros)} detalles")

    res.requests = client.requests_hechos - base
    return res


def registrar_corrida(res: Resumen, client: MercadoPublicoClient, bitacora: Path = BITACORA) -> dict:
    """Agrega una línea con el resumen de la corrida (sin secretos) a la bitácora versionada.
    Permite revisar el uso del cupo y los rechazos de la API sin acceso a los logs de Actions."""
    fila = {
        "fin": datetime.now(TZ_CHILE).isoformat(timespec="seconds"),
        "requests": res.requests,
        "descargados": res.descargados,
        "requests_por_licitacion": round(res.requests / res.descargados, 2) if res.descargados else None,
        "requests_por_dia": res.requests_por_dia,
        "dias_completos": len(res.dias_completos),
        "fallidos": res.fallidos,
        "motivo_fin": res.motivo_fin,
        "error": res.error,
        "respuestas_http": dict(client.respuestas),
        "pausa_final_s": round(client.pausa_s, 2),
    }
    bitacora.parent.mkdir(parents=True, exist_ok=True)
    with bitacora.open("a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tope", type=int, default=TOPE_REQUESTS, help="máximo de requests en esta corrida")
    p.add_argument("--max-minutos", type=float, default=240)
    p.add_argument("--madurez", type=int, default=MADUREZ_DIAS, help="días mínimos desde la publicación")
    p.add_argument("--pausa", type=float, default=1.0, help="segundos base entre requests")
    a = p.parse_args(argv)
    client = MercadoPublicoClient(pausa_s=a.pausa)
    usados = usos_previos()
    print(f"Requests ya usados por día (bitácora): {usados}")
    res = extraer_detalle(client, tope=a.tope, max_minutos=a.max_minutos, madurez=a.madurez, usados_por_dia=usados)
    print(f"Respuestas HTTP: {dict(client.respuestas)} · pausa final: {client.pausa_s:.2f}s")
    registrar_corrida(res, client)
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
