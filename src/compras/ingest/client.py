"""Cliente mínimo para la API pública de Mercado Público (ChileCompra).

Docs: https://www.chilecompra.cl/api/  · Límite: 10.000 requests/día por ticket.
"""
from __future__ import annotations

import os
import time
from datetime import date

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"


def fecha_api(d: date) -> str:
    """La API espera fechas como ddmmaaaa."""
    return d.strftime("%d%m%Y")


class MercadoPublicoClient:
    def __init__(self, ticket: str | None = None, pausa_s: float = 0.5, session: requests.Session | None = None):
        load_dotenv()
        self.ticket = ticket or os.getenv("MERCADO_PUBLICO_TICKET")
        if not self.ticket:
            raise ValueError("Falta MERCADO_PUBLICO_TICKET (ver .env.example)")
        self.pausa_s = pausa_s
        self.session = session or requests.Session()
        self.requests_hechos = 0

    def _get(self, recurso: str, params: dict, reintentos: int = 3) -> dict:
        params = {**params, "ticket": self.ticket}
        ultimo_error = "sin respuesta"
        for intento in range(reintentos):
            try:
                resp = self.session.get(f"{BASE_URL}/{recurso}", params=params, timeout=30)
            except requests.RequestException as e:
                ultimo_error = self._sin_ticket(str(e))
            else:
                self.requests_hechos += 1
                if resp.status_code == 200:
                    time.sleep(self.pausa_s)
                    return resp.json()
                ultimo_error = f"HTTP {resp.status_code}"
            time.sleep(2 ** intento)  # backoff ante errores/limitación
        # `from None` evita que la traza original (con la URL y el ticket) llegue a los logs
        raise ConnectionError(f"Fallo al consultar {recurso}: {ultimo_error}") from None

    def _sin_ticket(self, texto: str) -> str:
        """Nunca exponer el ticket en mensajes de error ni logs."""
        return texto.replace(self.ticket, "***")

    def licitaciones_por_fecha(self, d: date) -> list[dict]:
        """Listado (resumen) de licitaciones publicadas en una fecha."""
        data = self._get("licitaciones.json", {"fecha": fecha_api(d)})
        return data.get("Listado", [])

    def licitacion(self, codigo: str) -> dict | None:
        """Detalle completo de una licitación por su código."""
        data = self._get("licitaciones.json", {"codigo": codigo})
        listado = data.get("Listado", [])
        return listado[0] if listado else None
