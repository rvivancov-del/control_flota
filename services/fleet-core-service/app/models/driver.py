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
    # Credencial personal del portal de despacho por QR (RF-18): sustituye
    # al login JWT para un conductor que solo escanea el código pegado en su
    # cabina. Solo se guarda el SHA-256 del token (el token en claro se
    # muestra una única vez al emitirlo), con fecha de emisión, vigencia y
    # último uso; NULL = sin credencial (nunca emitida o revocada).
    # Ver app/despacho/qr_token.py.
    qr_token_hash = Column(String(64), unique=True, nullable=True)
    qr_token_issued_at = Column(DateTime(timezone=True), nullable=True)
    qr_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    qr_token_last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def has_qr(self) -> bool:
        """True si el conductor tiene una credencial de despacho emitida."""
        return self.qr_token_hash is not None
