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
    # RF-18: el token del QR NO se devuelve aquí (solo se guarda su hash);
    # únicamente el estado de la credencial, para que el panel muestre si el
    # conductor tiene QR, cuándo vence y cuándo se usó por última vez.
    has_qr: bool
    qr_token_expires_at: Optional[datetime]
    qr_token_last_used_at: Optional[datetime]
    created_at: Optional[datetime]


class DriverQrIssued(DriverRead):
    """Respuesta al emitir una credencial (alta de conductor o regenerar QR):
    es la única vez que el token viaja en claro; no se puede volver a consultar."""

    qr_token: str
