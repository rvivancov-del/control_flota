"""Cliente HTTP hacia fleet-core-service -- la única forma en que
reporting-service obtiene datos, al no tener base de datos propia.

Todas las llamadas de un proceso comparten un pool de conexiones (keep-alive): abrir una conexión nueva
por llamada, como se hacía antes, multiplicaba el costo de cada consulta del tablero. Como toda consulta
es un GET (idempotente), se reintenta con espera creciente cuando fleet-core no contesta a tiempo o
responde 502/503/504; un error del cliente (401, 403, 404, 422) nunca se reintenta.
"""
import os
import threading
import time
from datetime import date
from typing import Optional

import httpx

FLEET_SERVICE_BASE_URL = os.getenv("FLEET_SERVICE_BASE_URL", "http://fleet-core-service:8000")

CONNECT_TIMEOUT_S = float(os.getenv("FLEET_CONNECT_TIMEOUT_S", "3"))
READ_TIMEOUT_S = float(os.getenv("FLEET_READ_TIMEOUT_S", "10"))
MAX_RETRIES = int(os.getenv("FLEET_MAX_RETRIES", "2"))  # reintentos, además del primer intento
BACKOFF_BASE_S = float(os.getenv("FLEET_BACKOFF_BASE_S", "0.2"))  # espera: 0,2 s, 0,4 s, ...
RETRY_STATUS = (502, 503, 504)
# Fallos de red de una conexión que no llegó a procesar la petición (o que el servidor ya había cerrado).
# No se reintentan los tiempos de espera de lectura: duplicarían la espera del usuario y la carga.
RETRY_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.ReadError)

_sleep = time.sleep  # sustituible en las pruebas para no esperar de verdad
_client: Optional[httpx.Client] = None
_client_lock = threading.Lock()


def _http() -> httpx.Client:
    """Cliente compartido del proceso (httpx.Client es seguro entre hilos); se crea al primer uso."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    base_url=FLEET_SERVICE_BASE_URL,
                    timeout=httpx.Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
                    limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
                )
    return _client


def close() -> None:
    """Cierra el pool al apagar el servicio."""
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


class FleetClient:
    """Cliente HTTP hacia fleet-core-service. reporting-service no tiene
    acceso directo al esquema "fleet" — respeta el límite entre servicios
    consultando su API, con el mismo token del usuario que hizo la petición
    original a este servicio. El token va en cada llamada, no en el pool:
    ninguna conexión queda asociada a un usuario."""

    def __init__(self, token: str) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}

    def _get(self, path: str, params: Optional[dict] = None):
        attempt = 0
        while True:
            try:
                response = _http().get(path, headers=self._headers, params=params)
            except RETRY_ERRORS:
                if attempt >= MAX_RETRIES:
                    raise
            else:
                if response.status_code not in RETRY_STATUS or attempt >= MAX_RETRIES:
                    response.raise_for_status()
                    return response.json()
            attempt += 1
            _sleep(BACKOFF_BASE_S * 2 ** (attempt - 1))

    def list_vehicles(self) -> list[dict]:
        return self._get("/vehicles")

    def list_drivers(self) -> list[dict]:
        return self._get("/drivers")

    def list_maintenance_records(
        self, vehicle_id: Optional[str] = None, status_filter: Optional[str] = None
    ) -> list[dict]:
        """Mantenimientos de toda la flota (o de un vehículo, o de un estado) en UNA sola llamada, con
        km restantes y urgencia ya calculados por fleet-core. Reemplaza al historial pedido vehículo por
        vehículo, cuya cantidad de llamadas crecía con el tamaño de la flota."""
        params: dict = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if status_filter:
            params["status_filter"] = status_filter
        return self._get("/maintenance", params=params or None)

    def list_maintenance_alerts(self) -> list[dict]:
        return self._get("/maintenance/alerts")

    def maintenance_policy(self) -> dict:
        """Política de alertas de RF-13 (umbral 'próximo'), única fuente en fleet-core."""
        return self._get("/maintenance/policy")

    def _period_params(self, date_from: Optional[date], date_to: Optional[date]) -> dict:
        params: dict = {}
        if date_from is not None:
            params["date_from"] = date_from.isoformat()
        if date_to is not None:
            params["date_to"] = date_to.isoformat()
        return params

    def expense_aggregate(self, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[dict]:
        """Gasto por (vehículo, conductor, fecha, tipo), ya sumado en SQL —
        una sola llamada en vez de una por viaje."""
        return self._get("/analytics/expenses", params=self._period_params(date_from, date_to))

    def trip_aggregate(self, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[dict]:
        """Viajes y kilometraje por (vehículo, conductor, fecha), ya sumado en SQL."""
        return self._get("/analytics/trips", params=self._period_params(date_from, date_to))

    def maintenance_aggregate(self, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[dict]:
        """Costo de mantenimiento completado por (vehículo, fecha, categoría, tipo), ya sumado en SQL."""
        return self._get("/analytics/maintenance", params=self._period_params(date_from, date_to))

    def fixed_cost_accrual(self, date_from: date, date_to: date) -> list[dict]:
        """Costos fijos devengados en el período, por (vehículo, categoría), prorrateados por días.
        Solo el rol admin puede pedirlos: con otro rol fleet-core responde 403."""
        return self._get("/analytics/fixed-costs", params=self._period_params(date_from, date_to))

    def personnel_cost_accrual(self, date_from: date, date_to: date) -> list[dict]:
        """Costos de personal devengados en el período, por (conductor, concepto), prorrateados por días (solo admin)."""
        return self._get("/analytics/personnel-costs", params=self._period_params(date_from, date_to))

    def route_aggregate(self, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[dict]:
        """Costo y distancia promedio por ruta (origen-destino), ya sumado en SQL."""
        return self._get("/analytics/routes", params=self._period_params(date_from, date_to))
