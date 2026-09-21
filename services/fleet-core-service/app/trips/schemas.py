"""Esquemas del ciclo de vida de un viaje, incluida la respuesta combinada
del cierre (viaje + alertas de mantenimiento disparadas)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

TRIP_STATUSES = {"planificado", "en_curso", "completado", "anulado"}


class TripCreate(BaseModel):
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    origin: str
    destination: str
    departure_at: datetime
    start_mileage_km: int


class TripRevenueUpdate(BaseModel):
    revenue: Decimal


class TripClose(BaseModel):
    end_mileage_km: int
    arrival_at: datetime
    # RF-16 extendido: el ingreso (flete cobrado) se conoce al cerrar el
    # viaje, igual que el kilometraje final. Opcional — no todo viaje
    # histórico tiene el dato, y no forzar el campo evita bloquear el cierre.
    revenue: Optional[Decimal] = None


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    created_by: Optional[uuid.UUID]
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: Optional[datetime]
    start_mileage_km: int
    end_mileage_km: Optional[int]
    revenue: Optional[Decimal]
    status: str
    remission_guide: Optional[str]
    cargo_type: Optional[str]
    notes: Optional[str]
    created_at: Optional[datetime]

    @computed_field
    @property
    def km_recorridos(self) -> Optional[int]:
        """RF-07: calculado a partir del kilometraje inicial y final, no almacenado."""
        if self.end_mileage_km is None:
            return None
        return self.end_mileage_km - self.start_mileage_km


class MaintenanceAlertBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    maintenance_type: str
    category: str
    scheduled_mileage_km: Optional[int]
    km_remaining: Optional[int] = None
    urgency: Optional[str] = None  # "vencido" | "proximo" (RF-13)


class TripCloseResult(BaseModel):
    trip: TripRead
    maintenance_alerts: list[MaintenanceAlertBrief]
