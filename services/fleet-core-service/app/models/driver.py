"""Modelo ORM de la tabla fleet.drivers."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Driver(Base):
    """Conductor de la flota (Lámina D-01). RF-05, RF-18 (despacho por QR)."""

    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(120), nullable=False)
    license_number = Column(String(20), unique=True, nullable=False)
    license_type = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="activo", server_default="activo")
    # Vehículo por defecto de este conductor — precarga el portal de
    # despacho móvil (RF-18). No impide registrar un viaje con otro
    # vehículo desde el panel de administración.
    assigned_vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)
    # Token opaco para el flujo de despacho por código QR: sustituye al
    # login JWT normal para un conductor que solo escanea un código pegado
    # en la cabina — no es una contraseña, es una capacidad de un solo uso
    # por conductor (RF-18).
    qr_token = Column(String(64), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
