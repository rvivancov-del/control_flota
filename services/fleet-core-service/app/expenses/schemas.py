"""Esquemas de gastos: alta, edición y lectura, con validación del tipo."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_TYPES = {"combustible", "peaje", "alimentacion"}


class ExpenseCreate(BaseModel):
    type: str
    amount: Decimal
    # Litros cargados — solo tiene sentido cuando type="combustible"; se
    # ignora (queda null) para los demás tipos.
    liters: Optional[Decimal] = None
    currency: str = "USD"
    expense_date: date
    notes: Optional[str] = None
    receipt_url: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, value: str) -> str:
        if value not in ALLOWED_TYPES:
            raise ValueError(f"type debe ser uno de: {', '.join(sorted(ALLOWED_TYPES))}")
        return value


class ExpenseUpdate(BaseModel):
    amount: Optional[Decimal] = None
    liters: Optional[Decimal] = None
    notes: Optional[str] = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trip_id: uuid.UUID
    type: str
    amount: Decimal
    liters: Optional[Decimal]
    currency: str
    expense_date: date
    notes: Optional[str]
    receipt_url: Optional[str]
    created_at: Optional[datetime]
