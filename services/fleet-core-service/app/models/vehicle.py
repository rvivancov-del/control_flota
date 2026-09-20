"""Modelo ORM de la tabla fleet.vehicles."""
import uuid

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Vehicle(Base):
    """Vehículo de la flota (Lámina D-01). RF-04."""

    __tablename__ = "vehicles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plate = Column(String(10), unique=True, nullable=False)
    brand = Column(String(60), nullable=False)
    model = Column(String(60), nullable=False)
    year = Column(Integer, nullable=False)
    # Matrícula (documento de registro vehicular anual) — distinta de la
    # placa; se muestra en la tarjeta de cabina del portal de despacho.
    registration_number = Column(String(30), nullable=True)
    current_mileage_km = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="activo")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
