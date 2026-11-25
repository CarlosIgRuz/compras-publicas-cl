"""Paridad: el modelo exportado al navegador (modelo.js) predice lo mismo que LightGBM en Python."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("lightgbm")
NODE = shutil.which("node")
JS = Path(__file__).resolve().parents[1] / "src/compras/api/static/modelo.js"

RUNNER = """
const m = require(process.argv[2]);
const modelo = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const casos = JSON.parse(require('fs').readFileSync(process.argv[4], 'utf8'));
console.log(JSON.stringify(casos.map(c => { const r = m.predecir(modelo, c); return [r.probabilidad_desierta, r.nivel]; })));
"""


def casos(meta, organismos, n=400, semilla=0):
    rng = np.random.default_rng(semilla)
    cats = meta["categorias"]
    out = []
    for i in range(n):
        elegir = lambda lista, extra: (lista + extra)[rng.integers(0, len(lista) + len(extra))]
        out.append({
            "tipo": elegir(cats["tipo"], ["ZZ"]),
            "rubro_principal": elegir(cats["rubro_principal"], ["Rubro nunca visto", None]),
            "region": elegir(cats["region"], [None]),
            "moneda": elegir(["CLP", "CLP", "USD", "UF"], []),
            "n_items": int(rng.integers(1, 60)), "n_rubros": 1,
            "monto_estimado_clp": None if i % 4 == 0 else float(rng.lognormal(16, 1.5)),
            "monto_visible": [None, True, False][i % 3],
            "etapas": [None, 1, 2][i % 3],
            "codigo_organismo": elegir(organismos, [None, "no-existe"]),
            "fecha_publicacion": f"2026-10-{1 + i % 28:02d}T{(i * 7) % 24:02d}:15:00",
        })
    return out


def paridad(carpeta: Path, tmp_path: Path):
    from compras.api.app import Licitacion, Modelo
    from compras.deploy.web import exportar_web

    modelo_json = tmp_path / "modelo.json"
    modelo_json.write_text(json.dumps(exportar_web(carpeta)), encoding="utf-8")
    m = Modelo(carpeta)
    lista = casos(m.meta, list(m.hist_org)[:50])
    (tmp_path / "casos.json").write_text(json.dumps(lista), encoding="utf-8")
    (tmp_path / "runner.js").write_text(RUNNER, encoding="utf-8")
    salida = subprocess.run([NODE, str(tmp_path / "runner.js"), str(JS), str(modelo_json), str(tmp_path / "casos.json")],
                            capture_output=True, text=True, check=True).stdout
    js = json.loads(salida)
    py = [m.predecir(Licitacion(**c)) for c in lista]
    dif = max(abs(a[0] - b.probabilidad_desierta) for a, b in zip(js, py))
    assert dif < 1e-4, dif  # la API redondea a 4 decimales
    assert [a[1] for a in js] == [b.nivel for b in py]


@pytest.mark.skipif(NODE is None, reason="requiere node")
def test_paridad_modelo_sintetico(artefactos, tmp_path):
    paridad(artefactos, tmp_path)


@pytest.mark.skipif(NODE is None or not Path("artifacts/modelo/lightgbm.txt").exists(), reason="requiere node y el modelo real")
def test_paridad_modelo_real(tmp_path):
    paridad(Path("artifacts/modelo"), tmp_path)
