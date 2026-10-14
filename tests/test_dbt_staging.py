"""Corre `dbt build` sobre datos crudos de juguete y verifica el staging."""
import gzip
import json
from pathlib import Path

import pytest

dbt_main = pytest.importorskip("dbt.cli.main")
duckdb = pytest.importorskip("duckdb")

DBT_DIR = Path(__file__).resolve().parents[1] / "dbt"


def escribir(dir_: Path, nombre: str, filas: list[dict]):
    dir_.mkdir(parents=True, exist_ok=True)
    with gzip.open(dir_ / nombre, "wt", encoding="utf-8") as f:
        json.dump(filas, f)


def test_stg_listados(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    escribir(raw / "licitaciones", "fecha=2026-07-01.json.gz", [
        {"CodigoExterno": "1-1-LE26", "Nombre": "A", "CodigoEstado": 7, "FechaCierre": "2026-07-01T15:04:02.1"},
        # misma licitación repetida en el día con otros milisegundos: debe quedar una
        {"CodigoExterno": "1-1-LE26", "Nombre": "A", "CodigoEstado": 7, "FechaCierre": "2026-07-01T15:04:09.9"},
        {"CodigoExterno": "2-5-LP26", "Nombre": "B", "CodigoEstado": 15, "FechaCierre": None},
    ])
    escribir(raw / "licitaciones", "fecha=2026-07-02.json.gz", [])  # día vacío (domingo)
    db = tmp_path / "w.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(db))

    res = dbt_main.dbtRunner().invoke([
        "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR),
        "--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs"),
        "--vars", json.dumps({"raw_dir": str(raw)}),
    ])
    assert res.success

    filas = duckdb.connect(str(db)).sql(
        "select codigo, estado, tipo, fecha_cierre from stg_listados order by codigo"
    ).fetchall()
    assert [(c, e, t) for c, e, t, _ in filas] == [
        ("1-1-LE26", "desierta", "LE"),
        ("2-5-LP26", "no_documentado_15", "LP"),
    ]
    assert str(filas[0][3]).startswith("2026-07-01 15:04:09")
