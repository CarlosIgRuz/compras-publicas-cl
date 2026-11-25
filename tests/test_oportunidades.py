from datetime import datetime

import pandas as pd

from compras.monitor import oportunidades as o


def publicadas():
    filas = []
    for i in range(40):  # rubro A: 40 recientes con riesgo alto
        filas.append({"codigo": f"A{i}", "nombre": f"Compra A{i}", "organismo": "Muni", "rubro_principal": "A",
                      "fecha_publicacion": "2026-11-20 10:00:00", "fecha_cierre": "2026-12-01 15:00:00",
                      "probabilidad": 0.4 + i / 1000, "nivel": "alto"})
    for i in range(40):  # rubro B: 40 recientes con riesgo bajo; dos ya cerradas
        filas.append({"codigo": f"B{i}", "nombre": f"Compra B{i}", "organismo": "Hospital", "rubro_principal": "B",
                      "fecha_publicacion": "2026-11-21 10:00:00",
                      "fecha_cierre": "2026-11-22 15:00:00" if i < 2 else "2026-12-02 15:00:00",
                      "probabilidad": 0.9 if i < 2 else 0.1, "nivel": "alto" if i < 2 else "bajo"})
    for i in range(10):  # rubro C: muy pocas → fuera del ranking
        filas.append({"codigo": f"C{i}", "nombre": "x", "organismo": "y", "rubro_principal": "C",
                      "fecha_publicacion": "2026-11-21 10:00:00", "fecha_cierre": "2026-12-02 15:00:00",
                      "probabilidad": 0.99, "nivel": "alto"})
    for i in range(40):  # rubro D: fuera de la ventana de 28 días
        filas.append({"codigo": f"D{i}", "nombre": "x", "organismo": "y", "rubro_principal": "D",
                      "fecha_publicacion": "2026-09-01 10:00:00", "fecha_cierre": "2026-09-10 15:00:00",
                      "probabilidad": 0.95, "nivel": "alto"})
    return pd.DataFrame(filas)


def test_ranking_rubros_ordena_y_filtra():
    hist = pd.DataFrame({"rubro": ["A", "B"], "tasa_desierta": [0.33, 0.1], "oferentes_mediana": [2.0, 5.0]})
    r = o.ranking_rubros(publicadas(), hist, pd.Timestamp("2026-11-21 10:00:00"))
    assert [x["rubro"] for x in r] == ["A", "B"]  # C tiene < 30 publicadas, D está fuera de la ventana
    assert r[0]["publicadas"] == 40 and r[0]["pct_alto"] == 1.0 and r[0]["oferentes_mediana"] == 2.0


def test_abiertas_solo_las_que_no_han_cerrado():
    top = o.abiertas_riesgosas(publicadas(), datetime(2026, 11, 25, 12, 0))
    codigos = [x["codigo"] for x in top]
    assert "B0" not in codigos and "B1" not in codigos  # alta probabilidad, pero ya cerraron
    assert not any(c.startswith("D") for c in codigos)
    assert codigos[0] == "C0" and len(top) == o.TOP_ABIERTAS
    assert top[0]["url"].endswith("idlicitacion=C0")
