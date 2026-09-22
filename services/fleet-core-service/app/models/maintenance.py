"""Modelo ORM de la tabla fleet.maintenance_records."""
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class MaintenanceRecord(Base):
    """Registro de mantenimiento de un vehículo (Lámina D-01). RF-11, RF-12, RF-13."""

    __tablename__ = "maintenance_records"
    __table_args__ = (
        # Historial de un vehículo y sus pendientes (alertas, GET /maintenance y /vehicles/{id}/maintenance).
        Index("ix_maintenance_records_vehicle_id_status", "vehicle_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    # aceite | filtros | llantas | frenos | bocines | otro
    maintenance_type = Column(String(20), nullable=False)
    # preventivo | correctivo | programado_km
    category = Column(String(20), nullable=False)
    scheduled_mileage_km = Column(Integer, nullable=True)
    performed_mileage_km = Column(Integer, nullable=True)
    cost = Column(Numeric(10, 2), nullable=True)
    performed_at = Column(Date, nullable=True)
    # pendiente | en_proceso | completado
    status = Column(String(20), nullable=False, default="pendiente")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vehicle = relationship("Vehicle")
