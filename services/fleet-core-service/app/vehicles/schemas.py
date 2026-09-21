"""Esquemas de alta, edición y lectura de vehículos."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_STATUS = {"activo", "mantenimiento", "inactivo"}


def _validate_status(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in ALLOWED_STATUS:
        raise ValueError(f"status debe ser uno de: {', '.join(sorted(ALLOWED_STATUS))}")
    return value


class VehicleCreate(BaseModel):
    plate: str
    brand: str
    model: str
    year: int
    current_mileage_km: int = Field(default=0, ge=0)
    status: str = "activo"
    registration_number: Optional[str] = None

    _check_status = field_validator("status")(_validate_status)


class VehicleUpdate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    current_mileage_km: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None
    registration_number: Optional[str] = None

    _check_status = field_validator("status")(_validate_status)


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
