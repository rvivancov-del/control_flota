"""Esquemas de gastos: alta, edición y lectura, con validación del tipo."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_TYPES = {"combustible", "peaje", "alimentacion"}


def _clean_location(value: Optional[str]) -> Optional[str]:
    """Recorta espacios; un texto vacío equivale a no informar la ubicación."""
    return (value.strip() or None) if value is not None else None


class ExpenseCreate(BaseModel):
    type: str
    amount: Decimal = Field(gt=0)
    # Litros cargados — solo tiene sentido cuando type="combustible"; se
    # ignora (queda null) para los demás tipos.
    liters: Optional[Decimal] = Field(default=None, gt=0)
    currency: str = "USD"
    expense_date: date
    # RF-09: ubicación del peaje; obligatoria cuando type="peaje", se descarta en los demás tipos.
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None
    receipt_url: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if value not in ALLOWED_TYPES:
            raise ValueError(f"type debe ser uno de: {', '.join(sorted(ALLOWED_TYPES))}")
        return value

    @model_validator(mode="after")
    def _location_rule(self) -> "ExpenseCreate":
        self.location = _clean_location(self.location)
        if self.type == "peaje" and self.location is None:
            raise ValueError("location es obligatoria para un peaje (RF-09)")
        if self.type != "peaje":
            self.location = None
        return self


class ExpenseUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=0)
    liters: Optional[Decimal] = Field(default=None, gt=0)
    location: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None

    _clean_location = field_validator("location")(_clean_location)


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    type: str
    amount: Decimal
    liters: Optional[Decimal]
    currency: str
    expense_date: date
    location: Optional[str]
    notes: Optional[str]
    receipt_url: Optional[str]
    created_at: Optional[datetime]


class ExpenseListRead(ExpenseRead):
    """Gasto con los datos de su viaje, para consultarlos sin abrir cada viaje (RF-14)."""

    vehicle_id: uuid.UUID
    driver_id: uuid.UUID
    origin: str
    destination: str
