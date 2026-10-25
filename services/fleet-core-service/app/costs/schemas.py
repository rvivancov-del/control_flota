"""Esquemas de los costos fijos por vehículo y de personal por conductor (modelo de costos)."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.costs import FIXED_COST_CATEGORIES, PERIODS, PERSONNEL_CONCEPTS


def _one_of(name: str, allowed: tuple[str, ...]):
    def check(value):
        if value is not None and value not in allowed:
            raise ValueError(f"{name} debe ser uno de: {', '.join(allowed)}")
        return value

    return check


_AMOUNT = Field(gt=0, max_digits=12, decimal_places=2)


class FixedCostCreate(BaseModel):
    vehicle_id: uuid.UUID
    category: str
    amount: Decimal = _AMOUNT
    period: str
    valid_from: date
    valid_to: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    _check_category = field_validator("category")(_one_of("category", FIXED_COST_CATEGORIES))
    _check_period = field_validator("period")(_one_of("period", PERIODS))

    @model_validator(mode="after")
    def _validity(self) -> "FixedCostCreate":
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("La fecha final de la vigencia no puede ser anterior a la inicial")
        return self


class FixedCostUpdate(BaseModel):
    category: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    period: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    _check_category = field_validator("category")(_one_of("category", FIXED_COST_CATEGORIES))
    _check_period = field_validator("period")(_one_of("period", PERIODS))


class FixedCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehicle_id: uuid.UUID
    category: str
    amount: Decimal
    period: str
    valid_from: date
    valid_to: Optional[date]
    notes: Optional[str]
    created_at: Optional[datetime]


class PersonnelCostCreate(BaseModel):
    driver_id: uuid.UUID
    concept: str
    amount: Decimal = _AMOUNT  # monto mensual
    valid_from: date
    valid_to: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    _check_concept = field_validator("concept")(_one_of("concept", PERSONNEL_CONCEPTS))

    @model_validator(mode="after")
    def _validity(self) -> "PersonnelCostCreate":
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("La fecha final de la vigencia no puede ser anterior a la inicial")
        return self


class PersonnelCostUpdate(BaseModel):
    concept: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    _check_concept = field_validator("concept")(_one_of("concept", PERSONNEL_CONCEPTS))


class PersonnelCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    concept: str
    amount: Decimal
    valid_from: date
    valid_to: Optional[date]
    notes: Optional[str]
    created_at: Optional[datetime]


class FixedCostAccrualRow(BaseModel):
    """Costo fijo devengado en un período, por vehículo y categoría (ya prorrateado por días)."""

    vehicle_id: uuid.UUID
    category: str
    amount: Decimal


class PersonnelCostAccrualRow(BaseModel):
    """Costo de personal devengado en un período, por conductor y concepto (ya prorrateado por días)."""

    driver_id: uuid.UUID
    concept: str
    amount: Decimal
