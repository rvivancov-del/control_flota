"""Modelo ORM de la tabla fleet.expenses."""
import uuid

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Expense(Base):
    """Gasto operativo asociado a un viaje (Lámina D-01). RF-08, RF-09, RF-10."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("location IS NULL OR type = 'peaje'", name="ck_expenses_location_only_toll"),
        # Gastos de un viaje (unión con trips en analytics y GET /trips/{id}/expenses), por fecha.
        Index("ix_expenses_trip_id_expense_date", "trip_id", "expense_date"),
        # Filtros por rango de fechas (analytics y RF-14).
        Index("ix_expenses_expense_date", "expense_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False)
    type = Column(String(20), nullable=False)  # combustible | peaje | alimentacion
    amount = Column(Numeric(10, 2), nullable=False)
    # Litros cargados — solo aplica a type="combustible". Permite calcular
    # consumo (L/100km), que es una señal distinta del costo (el precio del
    # diésel sube y baja; el consumo delata problemas mecánicos o de manejo).
    liters = Column(Numeric(8, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    expense_date = Column(Date, nullable=False)
    # RF-09: ubicación del peaje (nombre de la estación o tramo). Obligatoria al
    # registrar un peaje nuevo; los peajes históricos de la base piloto no la tienen.
    location = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    receipt_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip")
