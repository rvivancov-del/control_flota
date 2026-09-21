"""Cliente HTTP hacia fleet-core-service -- la única forma en que
reporting-service obtiene datos, al no tener base de datos propia."""
import os
from datetime import date
from typing import Optional

import httpx

FLEET_SERVICE_BASE_URL = os.getenv("FLEET_SERVICE_BASE_URL", "http://fleet-core-service:8000")


class FleetClient:
    """Cliente HTTP hacia fleet-core-service. reporting-service no tiene
    acceso directo al esquema "fleet" — respeta el límite entre servicios
    consultando su API, con el mismo token del usuario que hizo la petición
    original a este servicio."""

    def __init__(self, token: str) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}

    def _get(self, path: str, params: Optional[dict] = None):
        with httpx.Client(base_url=FLEET_SERVICE_BASE_URL, timeout=10.0) as client:
            response = client.get(path, headers=self._headers, params=params)
            response.raise_for_status()
            return response.json()

    def list_vehicles(self) -> list[dict]:
        return self._get("/vehicles")

    def list_drivers(self) -> list[dict]:
        return self._get("/drivers")

    def list_trips(
        self, vehicle_id: Optional[str] = None, status_filter: Optional[str] = None
    ) -> list[dict]:
        params: dict = {}
        if vehicle_id:
            params["vehicle_id"] = vehicle_id
        if status_filter:
            params["status_filter"] = status_filter
        return self._get("/trips", params=params)

    def list_expenses(self, trip_id: str) -> list[dict]:
        return self._get(f"/trips/{trip_id}/expenses")

    def list_maintenance(self, vehicle_id: str) -> list[dict]:
        return self._get(f"/vehicles/{vehicle_id}/maintenance")

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

    def route_aggregate(self, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[dict]:
        """Costo y distancia promedio por ruta (origen-destino), ya sumado en SQL."""
        return self._get("/analytics/routes", params=self._period_params(date_from, date_to))
