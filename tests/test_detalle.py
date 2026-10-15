import gzip
import json
from datetime import date, datetime

from compras.ingest.detalle import TZ_CHILE, dias_pendientes, en_horario_nocturno, extraer_detalle

NOCHE = datetime(2026, 10, 14, 23, 0, tzinfo=TZ_CHILE)
HOY = date(2026, 10, 14)


class ClienteFalso:
    def __init__(self, fallar_en: str | None = None):
        self.requests_hechos = 0
        self.pedidos: list[str] = []
        self.fallar_en = fallar_en

    def licitacion(self, codigo):
        self.requests_hechos += 1
        if codigo == self.fallar_en:
            raise ConnectionError("Fallo al consultar licitaciones.json: HTTP 500")
        self.pedidos.append(codigo)
        return {"CodigoExterno": codigo, "Estado": "Adjudicada"}


def crear_listados(tmp_path, dias: dict[str, list[str]]):
    listados = tmp_path / "listados"
    listados.mkdir()
    for d, codigos in dias.items():
        with gzip.open(listados / f"fecha={d}.json.gz", "wt", encoding="utf-8") as f:
            json.dump([{"CodigoExterno": c} for c in codigos], f)
    return listados, tmp_path / "detalle"


def leer_final(detalle, d):
    with gzip.open(detalle / f"fecha={d}.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)


def test_solo_dias_maduros(tmp_path):
    listados, detalle = crear_listados(tmp_path, {"2026-08-01": ["A"], "2026-08-20": ["B"], "2026-10-01": ["C"]})
    assert dias_pendientes(HOY, listados, detalle, madurez=60) == [date(2026, 8, 1)]


def test_descarga_completa_y_no_repite(tmp_path):
    listados, detalle = crear_listados(tmp_path, {"2026-07-01": ["A", "B", "A"], "2026-07-02": ["B", "C"]})
    c = ClienteFalso()
    res = extraer_detalle(c, ahora=NOCHE, listados_dir=listados, detalle_dir=detalle)
    assert c.pedidos == ["A", "B", "C"]  # sin duplicados dentro ni entre días
    assert [r["codigo"] for r in leer_final(detalle, "2026-07-01")] == ["A", "B"]
    assert [r["codigo"] for r in leer_final(detalle, "2026-07-02")] == ["C"]
    assert not list(detalle.glob("*.parcial.jsonl"))
    assert res.dias_completos == [date(2026, 7, 1), date(2026, 7, 2)]

    c2 = ClienteFalso()
    extraer_detalle(c2, ahora=NOCHE, listados_dir=listados, detalle_dir=detalle)
    assert c2.requests_hechos == 0


def test_tope_deja_checkpoint_y_se_retoma(tmp_path):
    listados, detalle = crear_listados(tmp_path, {"2026-07-01": ["A", "B", "C", "D", "E"]})
    c = ClienteFalso()
    res = extraer_detalle(c, ahora=NOCHE, tope=5, listados_dir=listados, detalle_dir=detalle)
    assert res.motivo_fin == "tope de requests"
    assert c.requests_hechos <= 5
    assert not (detalle / "fecha=2026-07-01.json.gz").exists()
    assert (detalle / "fecha=2026-07-01.parcial.jsonl").exists()

    c2 = ClienteFalso()
    extraer_detalle(c2, ahora=NOCHE, listados_dir=listados, detalle_dir=detalle)
    assert set(c.pedidos).isdisjoint(c2.pedidos)
    assert [r["codigo"] for r in leer_final(detalle, "2026-07-01")] == ["A", "B", "C", "D", "E"]


def test_error_de_api_corta_sin_perder_avance(tmp_path):
    listados, detalle = crear_listados(tmp_path, {"2026-07-01": ["A", "B", "C"]})
    res = extraer_detalle(ClienteFalso(fallar_en="B"), ahora=NOCHE, listados_dir=listados, detalle_dir=detalle)
    assert res.error and res.motivo_fin == "error de API"
    lineas = (detalle / "fecha=2026-07-01.parcial.jsonl").read_text().splitlines()
    assert [json.loads(x)["codigo"] for x in lineas] == ["A"]


def test_fuera_de_horario_reduce_tope(tmp_path):
    listados, detalle = crear_listados(tmp_path, {"2026-07-01": [f"X{i}" for i in range(300)]})
    c = ClienteFalso()
    mediodia = datetime(2026, 10, 14, 12, 0, tzinfo=TZ_CHILE)
    extraer_detalle(c, ahora=mediodia, tope=9000, listados_dir=listados, detalle_dir=detalle)
    assert c.requests_hechos <= 100


def test_horario_nocturno():
    assert en_horario_nocturno(datetime(2026, 10, 14, 22, 30, tzinfo=TZ_CHILE))
    assert en_horario_nocturno(datetime(2026, 10, 15, 6, 59, tzinfo=TZ_CHILE))
    assert not en_horario_nocturno(datetime(2026, 10, 15, 7, 0, tzinfo=TZ_CHILE))


def test_cliente_cuenta_respuestas_y_adapta_pausa(monkeypatch):
    import compras.ingest.client as cl

    monkeypatch.setattr(cl.time, "sleep", lambda s: None)

    class Resp:
        def __init__(self, code):
            self.status_code = code

        def json(self):
            return {"Listado": [{"CodigoExterno": "X"}]}

    class Sesion:
        def __init__(self, codigos):
            self.codigos = list(codigos)

        def get(self, url, params, timeout):
            return Resp(self.codigos.pop(0))

    c = cl.MercadoPublicoClient(ticket="t", pausa_s=1.0, session=Sesion([429, 200]))
    assert c.licitacion("X") == {"CodigoExterno": "X"}
    assert c.respuestas == {"429": 1, "200": 1}
    assert c.requests_hechos == 2
    assert c.pausa_s == 1.5  # se alargó tras el rechazo

    c.session = Sesion([200] * cl.MercadoPublicoClient.RACHA_PARA_ACORTAR)
    for _ in range(cl.MercadoPublicoClient.RACHA_PARA_ACORTAR):
        c.licitacion("X")
    assert c.pausa_s == 1.2  # se acorta de a poco, sin bajar de la base


def test_registrar_corrida(tmp_path):
    from compras.ingest.detalle import Resumen, registrar_corrida

    class C:
        respuestas = {"200": 90, "500": 10}
        pausa_s = 1.0

    fila = registrar_corrida(Resumen(descargados=90, requests=100, motivo_fin="tope de requests"), C(), tmp_path / "b.jsonl")
    assert fila["requests_por_licitacion"] == 1.11
    guardada = json.loads((tmp_path / "b.jsonl").read_text())
    assert guardada["respuestas_http"] == {"200": 90, "500": 10}


def test_cupo_diario_suma_lo_ya_usado(tmp_path):
    from compras.ingest import detalle as m

    listados, detalle = crear_listados(tmp_path, {"2026-07-01": [f"X{i}" for i in range(50)]})
    c = ClienteFalso()
    usados = {NOCHE.date().isoformat(): m.CUPO_DIARIO - 10}
    res = extraer_detalle(c, ahora=NOCHE, listados_dir=listados, detalle_dir=detalle, usados_por_dia=usados)
    assert res.motivo_fin == "cupo diario"
    assert c.requests_hechos <= 10
    assert res.requests_por_dia == {NOCHE.date().isoformat(): c.requests_hechos}


def test_se_detiene_a_las_7(tmp_path):
    from datetime import timedelta

    listados, detalle = crear_listados(tmp_path, {"2026-07-01": [f"X{i}" for i in range(10)]})
    t = [datetime(2026, 10, 15, 6, 59, 57, tzinfo=TZ_CHILE)]

    def reloj():
        t[0] += timedelta(seconds=1)
        return t[0]

    c = ClienteFalso()
    res = extraer_detalle(c, ahora=t[0], reloj=reloj, listados_dir=listados, detalle_dir=detalle)
    assert res.motivo_fin == "fin del horario nocturno"
    assert c.requests_hechos == 2  # 06:59:58 y 06:59:59; a las 07:00:00 se detiene


def test_usos_previos_desde_bitacora(tmp_path):
    from compras.ingest.detalle import usos_previos

    b = tmp_path / "b.jsonl"
    b.write_text(
        json.dumps({"requests_por_dia": {"2026-10-14": 100, "2026-10-15": 50}}) + "\n"
        + json.dumps({"requests": 9000}) + "\n"  # corrida antigua sin desglose
        + json.dumps({"requests_por_dia": {"2026-10-15": 25}}) + "\n"
    )
    assert usos_previos(b) == {"2026-10-14": 100, "2026-10-15": 75}
    assert usos_previos(tmp_path / "no-existe.jsonl") == {}
