"""Modelos ORM de los costos fijos por vehículo y los costos de personal por conductor (Fase 3).

El prototipo original solo registraba costos variables por viaje (combustible, peajes,
alimentación) y de mantenimiento. La literatura separa el costo total en variable y fijo
(Poliak et al., 2025: Ct = Cv + Cf) y estructura el costo por kilómetro en ocho categorías
(Zysińska & Menes, 2026); sin depreciación, capital, seguros, impuestos y personal los
indicadores por kilómetro y el margen no son calculables. Estas dos tablas los aportan.
"""
import uuid

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# Categorías de costo fijo del vehículo y su correspondencia con las ocho categorías de
# Zysińska & Menes (2026); la tabla completa vive en reporting-service (cost_model.py).
FIXED_COST_CATEGORIES = ("depreciacion", "capital", "seguro", "impuestos", "otros")
PERSONNEL_CONCEPTS = ("sueldo", "beneficios_sociales", "otros")
PERIODS = ("mensual", "anual")


def _in_list(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


class FixedCost(Base):
    """Costo fijo de un vehículo: no depende del kilometraje recorrido en el período.
    Se registra como un monto mensual o anual con su vigencia y se prorratea por días."""

    __tablename__ = "fixed_costs"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_fixed_costs_amount_positive"),
        CheckConstraint(f"category IN ({_in_list(FIXED_COST_CATEGORIES)})", name="ck_fixed_costs_category"),
        CheckConstraint(f"period IN ({_in_list(PERIODS)})", name="ck_fixed_costs_period"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_fixed_costs_validity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    category = Column(String(20), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    period = Column(String(10), nullable=False)  # mensual | anual: a qué lapso corresponde `amount`
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)  # NULL = sigue vigente
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PersonnelCost(Base):
    """Costo de personal de un conductor (sueldo y beneficios sociales), siempre mensual.
    Es información financiera y personal: solo la administra y la ve el rol admin."""

    __tablename__ = "personnel_costs"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_personnel_costs_amount_positive"),
        CheckConstraint(f"concept IN ({_in_list(PERSONNEL_CONCEPTS)})", name="ck_personnel_costs_concept"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_personnel_costs_validity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False)
    concept = Column(String(20), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)  # monto mensual
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
