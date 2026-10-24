"""El historial del organismo en ml_licitaciones no debe usar resultados posteriores a la publicación."""
import gzip
import json
from pathlib import Path

import pytest

dbt_main = pytest.importorskip("dbt.cli.main")
duckdb = pytest.importorskip("duckdb")

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"


def escribir(dir_: Path, nombre: str, filas: list):
    dir_.mkdir(parents=True, exist_ok=True)
    with gzip.open(dir_ / nombre, "wt", encoding="utf-8") as f:
        json.dump(filas, f)


def detalle(codigo, estado, publicacion, cierre):
    return {"codigo": codigo, "descargado": "2026-10-19T03:00:00-03:00", "detalle": {
        "CodigoEstado": estado, "Tipo": "LE", "Comprador": {"CodigoOrganismo": "ORG"},
        "Moneda": "CLP", "MontoEstimado": 1000000,
        "Fechas": {"FechaPublicacion": publicacion, "FechaCierre": cierre},
        "Adjudicacion": {"NumeroOferentes": 0 if estado == 7 else 3},
        "Items": {"Cantidad": 1, "Listado": [{"Correlativo": 1, "Categoria": "Salud / X"}]},
    }}


def test_historial_point_in_time(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    # A: publicada 1-abr, declarada desierta el 10-jun (archivo de detalle = día del último evento)
    escribir(raw / "detalle", "fecha=2026-06-10.json.gz", [detalle("A", 7, "2026-04-01T10:00:00", "2026-06-10T15:00:00")])
    # B: publicada 5-jun (antes de que A se resolviera) → no puede ver A
    escribir(raw / "detalle", "fecha=2026-06-25.json.gz", [detalle("B", 8, "2026-06-05T10:00:00", "2026-06-15T15:00:00")])
    # C: publicada 20-jun (después) → sí ve A, pero no B (resuelta el 25-jun)
    escribir(raw / "detalle", "fecha=2026-07-30.json.gz", [detalle("C", 8, "2026-06-20T10:00:00", "2026-07-01T15:00:00")])
    # listados: definen el último día disponible (para la cohorte)
    escribir(raw / "licitaciones", "fecha=2026-06-10.json.gz", [{"CodigoExterno": "A", "CodigoEstado": 7}])
    escribir(raw / "licitaciones", "fecha=2026-10-17.json.gz", [{"CodigoExterno": "Z", "CodigoEstado": 5}])
    # licitación recién publicada (detalle al publicar): debe aparecer en ml_publicadas
    escribir(raw / "detalle_publicacion", "fecha=2026-10-16.json.gz",
             [detalle("N", 5, "2026-10-16T09:00:00", "2026-10-30T15:00:00")])
    db = tmp_path / "w.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(db))
    res = dbt_main.dbtRunner().invoke([
        "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR),
        "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs"),
        "--vars", json.dumps({"raw_dir": str(raw)}),
    ])
    assert res.success

    filas = {r[0]: r[1:] for r in duckdb.connect(str(db)).execute(
        "select codigo, org_n_previas, round(org_tasa_desierta_previa, 4), en_cohorte from ml_licitaciones"
    ).fetchall()}
    p0, m = 0.207, 10
    assert filas["A"][:2] == (0, round(p0, 4))
    assert filas["B"][:2] == (0, round(p0, 4))                     # A aún no estaba resuelta
    assert filas["C"][:2] == (1, round((1 + m * p0) / (1 + m), 4))  # ve A (desierta), no B
    # cohorte: publicadas desde el 1-abr y con 120 días de seguimiento hasta el 17-oct (≤ 19-jun)
    assert filas["A"][2] and filas["B"][2] and not filas["C"][2]

    pub = duckdb.connect(str(db)).execute(
        "select codigo, estado_al_descargar, rubro_principal, n_items, codigo_organismo, monto_estimado_clp from ml_publicadas"
    ).fetchall()
    assert pub == [("N", "publicada", "Salud", 1, "ORG", 1000000.0)]
