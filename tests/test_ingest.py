from datetime import date

from compras.ingest.client import MercadoPublicoClient, fecha_api
from compras.ingest.extract import extraer


def test_fecha_api():
    assert fecha_api(date(2026, 9, 3)) == "03092026"


class ClienteFalso(MercadoPublicoClient):
    def __init__(self):
        self.requests_hechos = 0

    def licitaciones_por_fecha(self, d):
        self.requests_hechos += 1
        return [{"CodigoExterno": f"X-{d.isoformat()}"}]


def test_extraer_es_incremental(tmp_path):
    c = ClienteFalso()
    assert extraer(date(2026, 9, 1), date(2026, 9, 3), c, raw_dir=tmp_path) == 3
    assert extraer(date(2026, 9, 1), date(2026, 9, 4), c, raw_dir=tmp_path) == 1
    assert c.requests_hechos == 4


def test_errores_no_exponen_ticket():
    import requests
    import pytest

    class SesionRota:
        def get(self, url, params, timeout):
            raise requests.ConnectionError(f"fallo en {url}?ticket={params['ticket']}")

    c = MercadoPublicoClient(ticket="SECRETO-123", pausa_s=0, session=SesionRota())
    with pytest.raises(ConnectionError) as exc:
        c._get("licitaciones.json", {}, reintentos=1)
    assert "SECRETO-123" not in str(exc.value)
