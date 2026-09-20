"""Esquemas del portal de despacho por QR (RF-18)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class DespachoInfo(BaseModel):
    """Lo que el portal móvil precarga al escanear el QR — solo lectura."""

    driver_id: uuid.UUID
    driver_name: str
    driver_status: str
    vehicle_id: uuid.UUID
    vehicle_plate: str
    vehicle_brand: str
    vehicle_model: str
    vehicle_registration_number: Optional[str]
    vehicle_current_mileage_km: int


class DespachoCreate(BaseModel):
    origin: str
    destination: str
    departure_at: Optional[datetime] = None
    start_mileage_km: int
    remission_guide: Optional[str] = None
    cargo_type: Optional[str] = None
    notes: Optional[str] = None
    # Recarga de combustible en origen (opcional) — si se informa el monto,
    # se registra como gasto del viaje igual que desde el panel de admin.
    fuel_amount: Optional[Decimal] = None
    fuel_liters: Optional[Decimal] = None


class DespachoTripBrief(BaseModel):
    id: uuid.UUID
    origin: str
    destination: str
    departure_at: datetime
    status: str


class DespachoResult(BaseModel):
    trip: DespachoTripBrief
    message: str
