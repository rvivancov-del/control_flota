"""Modelo ORM de la tabla fleet.trips."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Trip(Base):
    """Viaje realizado por un vehículo y un conductor (Lámina D-01). RF-06, RF-07, RF-14."""

    __tablename__ = "trips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False)
    # Referencia al usuario que registró el viaje (esquema "auth", otro
    # servicio) — sin FK de base de datos entre esquemas: cada microservicio
    # es dueño exclusivo de su propio esquema (ver README de arquitectura).
    # Nulo cuando el viaje lo registra el propio conductor vía el portal de
    # despacho por QR (RF-18), sin sesión de administrador de por medio.
    created_by = Column(UUID(as_uuid=True), nullable=True)

    origin = Column(String(120), nullable=False)
    destination = Column(String(120), nullable=False)
    departure_at = Column(DateTime(timezone=True), nullable=False)
    arrival_at = Column(DateTime(timezone=True), nullable=True)
    start_mileage_km = Column(Integer, nullable=False)
    end_mileage_km = Column(Integer, nullable=True)
    # Campos de despacho operativo (RF-18): documento de guía de remisión,
    # tipo de carga transportada, y observaciones libres del conductor.
    remission_guide = Column(String(60), nullable=True)
    cargo_type = Column(String(120), nullable=True)
    notes = Column(String(500), nullable=True)
    # Ingreso (flete cobrado) de este viaje — se conoce al cerrar el viaje,
    # igual que el kilometraje final. Opcional: viajes históricos o aún no
    # facturados quedan en null, no en 0 (0 significaría "viaje sin cobro").
    revenue = Column(Numeric(10, 2), nullable=True)
    status = Column(String(20), nullable=False, default="planificado")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle")
    driver = relationship("Driver")
