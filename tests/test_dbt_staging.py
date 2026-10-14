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
    escribir(raw / "detalle", "fecha=2026-07-01.json.gz", [
        {"codigo": "1-1-LE26", "descargado": "2026-10-14T03:00:00-03:00", "detalle": {
            "CodigoEstado": 8, "Estado": "Adjudicada", "Tipo": "LE", "CodigoTipo": 1, "Nombre": "A",
            "Comprador": {"CodigoOrganismo": "7479", "NombreOrganismo": "HOSPITAL X", "RegionUnidad": "Región del Biobío ",
                          "NombreUsuario": "Persona Funcionaria"},
            "Moneda": "CLP", "MontoEstimado": None,
            "Fechas": {"FechaPublicacion": "2026-06-01T10:00:00", "FechaCierre": "2026-06-20T15:00:00",
                       "FechaAdjudicacion": "1900-01-01T00:00:00"},
            "Adjudicacion": {"NumeroOferentes": 3, "Tipo": 2},
            "Items": {"Cantidad": 2, "Listado": [
                # mismo ítem adjudicado a dos proveedores; el segundo con cantidad y monto invertidos
                {"Correlativo": 1, "Categoria": "Salud / Camillas", "Cantidad": 2.0,
                 "Adjudicacion": {"RutProveedor": "76.1-1", "Cantidad": 1.0, "MontoUnitario": 500.0}},
                {"Correlativo": 1, "Categoria": "Salud / Camillas", "Cantidad": 2.0,
                 "Adjudicacion": {"RutProveedor": "77.2-2", "Cantidad": 700.0, "MontoUnitario": 1.0}},
            ]},
        }},
        {"codigo": "2-5-LP26", "descargado": "2026-10-14T03:00:01-03:00", "detalle": {
            "CodigoEstado": 15, "Estado": "Revocada", "Comprador": {"CodigoOrganismo": "1"},
            "Fechas": {"FechaPublicacion": "2026-06-02T10:00:00"}, "Adjudicacion": None,
            "Items": {"Cantidad": 0, "Listado": []},
        }},
    ])
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
        ("2-5-LP26", "revocada", "LP"),
    ]
    assert str(filas[0][3]).startswith("2026-07-01 15:04:09")

    con = duckdb.connect(str(db))
    det = con.sql(
        "select codigo, estado, region, numero_oferentes, fecha_adjudicacion, monto_estimado "
        "from stg_detalle order by codigo"
    ).fetchall()
    assert det == [
        ("1-1-LE26", "adjudicada", "Región del Biobío", 3, None, None),  # 1900 → NULL, región sin espacio
        ("2-5-LP26", "revocada", None, None, None, None),
    ]
    columnas = [c[0] for c in con.sql("describe stg_detalle").fetchall()]
    assert not any("usuario" in c for c in columnas)  # sin datos personales de funcionarios

    items = con.sql(
        "select posicion, correlativo, rubro, rut_proveedor, monto_adjudicado from stg_detalle_items order by posicion"
    ).fetchall()
    assert items == [(1, 1, "Salud", "76.1-1", 500.0), (2, 1, "Salud", "77.2-2", 700.0)]

    # marts
    fct = con.sql(
        "select codigo, tiene_resultado, es_desierta, rubro_principal, n_items, n_proveedores_adjudicados, "
        "monto_adjudicado_clp, dias_abierta from fct_licitaciones order by codigo"
    ).fetchall()
    assert fct == [
        ("1-1-LE26", True, False, "Salud", 1, 2, 1200.0, 19),
        ("2-5-LP26", False, None, None, 0, 0, None, None),  # revocada: sin resultado → objetivo NULL
    ]
    assert con.sql("select count(*) from fct_adjudicaciones").fetchone() == (2,)
    org = con.sql("select codigo_organismo, tasa_desierta from dim_organismos order by 1").fetchall()
    assert org == [("1", None), ("7479", 0.0)]
