"""Esquemas de alta, edición y lectura de conductores."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DriverCreate(BaseModel):
    full_name: str
    license_number: str
    license_type: Optional[str] = None
    phone: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None


class DriverUpdate(BaseModel):
    full_name: Optional[str] = None
    license_type: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None


class DriverRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    license_number: str
    license_type: Optional[str]
    phone: Optional[str]
    status: str
    assigned_vehicle_id: Optional[uuid.UUID]
    # Secreto del portal de despacho por QR — solo lo ve quien administra
    # conductores (mismo control de acceso que el resto de este router).
    qr_token: Optional[str]
    created_at: Optional[datetime]
