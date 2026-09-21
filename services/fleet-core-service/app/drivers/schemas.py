"""Esquemas de alta, edición y lectura de conductores."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.drivers.licenses import normalize_license_type

ALLOWED_STATUS = {"activo", "inactivo"}


def _clean_text(value: Optional[str]) -> Optional[str]:
    return value.strip() if value is not None else None


class DriverCreate(BaseModel):
    full_name: str
    license_number: str
    license_type: Optional[str] = None
    phone: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None

    _check_license_type = field_validator("license_type")(normalize_license_type)
    _clean_name = field_validator("full_name", "license_number")(_clean_text)

    @field_validator("full_name", "license_number")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("no puede estar vacío")
        return value


class DriverUpdate(BaseModel):
    """RNF-11: todos los datos personales son rectificables, incluida la licencia."""

    full_name: Optional[str] = None
    license_number: Optional[str] = None
    license_type: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    assigned_vehicle_id: Optional[uuid.UUID] = None

    _check_license_type = field_validator("license_type")(normalize_license_type)
    _clean_name = field_validator("full_name", "license_number")(_clean_text)

    @field_validator("full_name", "license_number")
    @classmethod
    def _not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value:
            raise ValueError("no puede estar vacío")
        return value

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ALLOWED_STATUS:
            raise ValueError(f"status debe ser uno de: {', '.join(sorted(ALLOWED_STATUS))}")
        return value


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
    # RNF-11: no nulo cuando los datos personales fueron suprimidos (irreversible).
    anonymized_at: Optional[datetime]
    created_at: Optional[datetime]


class LicenseTypeRead(BaseModel):
    code: str
    description: str


class DriverQrIssued(DriverRead):
    """Respuesta al emitir una credencial (alta de conductor o regenerar QR):
    es la única vez que el token viaja en claro; no se puede volver a consultar."""

    qr_token: str
