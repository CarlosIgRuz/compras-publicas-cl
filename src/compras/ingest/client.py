"""Cliente mínimo para la API pública de Mercado Público (ChileCompra).

Docs: https://www.chilecompra.cl/api/  · Límite: 10.000 requests/día por ticket.
"""
from __future__ import annotations

import os
import time
from collections import Counter
from datetime import date

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico"


def fecha_api(d: date) -> str:
    """La API espera fechas como ddmmaaaa."""
    return d.strftime("%d%m%Y")


class MercadoPublicoClient:
    """Cuenta todas las respuestas por código HTTP (`respuestas`) y adapta la pausa entre requests:
    la alarga ante un rechazo (429/5xx) y la acorta de a poco tras una racha de respuestas OK."""

    PAUSA_MAX_S = 5.0
    RACHA_PARA_ACORTAR = 100

    def __init__(self, ticket: str | None = None, pausa_s: float = 0.5, session: requests.Session | None = None):
        load_dotenv()
        self.ticket = ticket or os.getenv("MERCADO_PUBLICO_TICKET")
        if not self.ticket:
            raise ValueError("Falta MERCADO_PUBLICO_TICKET (ver .env.example)")
        self.pausa_base_s = self.pausa_s = pausa_s
        self.session = session or requests.Session()
        self.requests_hechos = 0
        self.respuestas: Counter[str] = Counter()
        self._racha_ok = 0

    def _get(self, recurso: str, params: dict, reintentos: int = 3) -> dict:
        params = {**params, "ticket": self.ticket}
        ultimo_error = "sin respuesta"
        for intento in range(reintentos):
            try:
                resp = self.session.get(f"{BASE_URL}/{recurso}", params=params, timeout=30)
            except requests.RequestException as e:
                ultimo_error = self._sin_ticket(str(e))
                self.respuestas["red"] += 1
            else:
                self.requests_hechos += 1
                self.respuestas[str(resp.status_code)] += 1
                if resp.status_code == 200:
                    self._ok()
                    time.sleep(self.pausa_s)
                    return resp.json()
                ultimo_error = f"HTTP {resp.status_code}"
            self._rechazo()
            time.sleep(2 ** intento)  # backoff ante errores/limitación
        # `from None` evita que la traza original (con la URL y el ticket) llegue a los logs
        raise ConnectionError(f"Fallo al consultar {recurso}: {ultimo_error}") from None

    def _ok(self) -> None:
        self._racha_ok += 1
        if self._racha_ok >= self.RACHA_PARA_ACORTAR and self.pausa_s > self.pausa_base_s:
            self.pausa_s = max(self.pausa_base_s, self.pausa_s / 1.25)
            self._racha_ok = 0

    def _rechazo(self) -> None:
        self._racha_ok = 0
        self.pausa_s = min(self.PAUSA_MAX_S, max(self.pausa_s, 0.1) * 1.5)

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
