"""Esquemas de alta, edición y lectura de vehículos."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

ALLOWED_STATUS = {"activo", "mantenimiento", "inactivo"}


class VehicleCreate(BaseModel):
    plate: str
    brand: str
    model: str
    year: int
    current_mileage_km: int = 0
    status: str = "activo"
    registration_number: Optional[str] = None


class VehicleUpdate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    current_mileage_km: Optional[int] = None
    status: Optional[str] = None
    registration_number: Optional[str] = None


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plate: str
    brand: str
    model: str
    year: int
    current_mileage_km: int
    status: str
    registration_number: Optional[str]
    created_at: Optional[datetime]
