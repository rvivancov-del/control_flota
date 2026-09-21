"""Esquemas de mantenimiento: alta, completar, corregir costo y lectura."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_TYPES = {"aceite", "filtros", "llantas", "frenos", "bocines", "otro"}
ALLOWED_CATEGORIES = {"preventivo", "correctivo", "programado_km"}


class MaintenanceCreate(BaseModel):
    maintenance_type: str
    category: str
    scheduled_mileage_km: Optional[int] = None

    @field_validator("maintenance_type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if value not in ALLOWED_TYPES:
            raise ValueError(f"maintenance_type debe ser uno de: {', '.join(sorted(ALLOWED_TYPES))}")
        return value

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if value not in ALLOWED_CATEGORIES:
            raise ValueError(f"category debe ser uno de: {', '.join(sorted(ALLOWED_CATEGORIES))}")
        return value


class MaintenanceComplete(BaseModel):
    performed_mileage_km: int
    performed_at: date
    cost: Decimal


class MaintenanceCostUpdate(BaseModel):
    cost: Decimal


class MaintenanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    maintenance_type: str
    category: str
    scheduled_mileage_km: Optional[int]
    performed_mileage_km: Optional[int]
    cost: Optional[Decimal]
    performed_at: Optional[date]
    status: str
    created_at: Optional[datetime]
    # RF-13: solo en mantenimientos pendientes; los calcula app/maintenance/policy.py.
    km_remaining: Optional[int] = None
    urgency: Optional[str] = None  # "vencido" | "proximo" | "normal"


class MaintenancePolicyRead(BaseModel):
    """Política de alertas vigente (RF-13) y su procedencia."""

    version: str
    estado: str
    procedencia: str
    proximo_km: int
    proximo_km_por_tipo: dict[str, int]
