"""Filas de agregación SQL que consume reporting-service."""
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ExpenseAggregateRow(BaseModel):
    """Un día de gasto de un tipo, para un vehículo y su conductor — ya sumado
    en SQL. reporting-service reagrega estas filas (pocas: días x tipos x
    vehículos) en memoria por vehículo, por conductor o por semana/mes/año,
    en vez de traer cada gasto individual por HTTP."""

    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    expense_date: date
    type: str
    amount_total: Decimal
    liters_total: Decimal
    count: int


class TripAggregateRow(BaseModel):
    """Viajes completados de un día, agregados por vehículo y conductor.
    `end_mileage_km` es el odómetro más alto de ese día — sirve para ubicar
    los gastos de ese día en el eje de kilometraje del vehículo."""

    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    trip_date: date
    trip_count: int
    distance_km: int
    end_mileage_km: int
    revenue_total: Decimal


class RouteAggregateRow(BaseModel):
    """Costo y distancia promedio por ruta (origen-destino) — el contexto
    necesario para juzgar si un conductor caro lo es por su manejo o porque
    le tocan las rutas más exigentes."""

    origin: str
    destination: str
    trip_count: int
    avg_distance_km: int
    cost_total: Decimal


class MaintenanceAggregateRow(BaseModel):
    """Costo de mantenimiento completado, agregado por vehículo, fecha,
    categoría y tipo — el mantenimiento no se le atribuye a un conductor (no
    depende de quién conducía, sino del vehículo)."""

    vehicle_id: uuid.UUID
    performed_at: date
    category: str
    maintenance_type: str
    cost_total: Decimal
    count: int
