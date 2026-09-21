"""Mantenimiento preventivo/correctivo de vehículos y sus alertas por
kilometraje (RF-11, RF-12, RF-13). La clasificación vencido/próximo/normal
la decide app/maintenance/policy.py."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.maintenance import policy
from app.maintenance.schemas import (
    MaintenanceComplete,
    MaintenanceCostUpdate,
    MaintenanceCreate,
    MaintenancePolicyRead,
    MaintenanceRead,
)
from app.models.maintenance import MaintenanceRecord
from app.models.vehicle import Vehicle

router = APIRouter(tags=["maintenance"], dependencies=[Depends(get_current_user)])


def _read_with_urgency(record: MaintenanceRecord, current_mileage_km: int) -> MaintenanceRead:
    """MaintenanceRead con km restantes y urgencia (RF-13) según la política vigente."""
    item = MaintenanceRead.model_validate(record)
    item.km_remaining, item.urgency = policy.assess(record, current_mileage_km)
    return item


@router.post(
    "/vehicles/{vehicle_id}/maintenance",
    response_model=MaintenanceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance(
    vehicle_id: uuid.UUID, payload: MaintenanceCreate, db: Session = Depends(get_db)
) -> MaintenanceRead:
    """RF-11, RF-12: registro y clasificación de mantenimiento (preventivo,
    correctivo o programado por kilometraje)."""
    if db.get(Vehicle, vehicle_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado.")

    record = MaintenanceRecord(vehicle_id=vehicle_id, status="pendiente", **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return MaintenanceRead.model_validate(record)


@router.get("/vehicles/{vehicle_id}/maintenance", response_model=list[MaintenanceRead])
def list_vehicle_maintenance(
    vehicle_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[MaintenanceRead]:
    """Historial de mantenimientos de un vehículo, del más reciente al más antiguo."""
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado.")
    records = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.vehicle_id == vehicle_id)
        .order_by(MaintenanceRecord.created_at.desc())
        .all()
    )
    return [_read_with_urgency(r, vehicle.current_mileage_km) for r in records]


@router.patch("/maintenance/{maintenance_id}/complete", response_model=MaintenanceRead)
def complete_maintenance(
    maintenance_id: uuid.UUID, payload: MaintenanceComplete, db: Session = Depends(get_db)
) -> MaintenanceRead:
    """RF-11: marca un mantenimiento como completado."""
    record = db.get(MaintenanceRecord, maintenance_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Registro de mantenimiento no encontrado."
        )
    if record.status == "completado":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Este mantenimiento ya está completado."
        )

    record.performed_mileage_km = payload.performed_mileage_km
    record.performed_at = payload.performed_at
    record.cost = payload.cost
    record.status = "completado"
    db.commit()
    db.refresh(record)
    return MaintenanceRead.model_validate(record)


@router.patch("/maintenance/{maintenance_id}/cost", response_model=MaintenanceRead)
def update_maintenance_cost(
    maintenance_id: uuid.UUID, payload: MaintenanceCostUpdate, db: Session = Depends(get_db)
) -> MaintenanceRead:
    """Corrige el costo de un mantenimiento ya completado (ej. factura corregida)."""
    record = db.get(MaintenanceRecord, maintenance_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Registro de mantenimiento no encontrado."
        )
    record.cost = payload.cost
    db.commit()
    db.refresh(record)
    return MaintenanceRead.model_validate(record)


@router.get("/maintenance/policy", response_model=MaintenancePolicyRead)
def get_maintenance_policy() -> MaintenancePolicyRead:
    """RF-13: umbral de alerta vigente y su procedencia (única fuente para
    reporting y frontend)."""
    p = policy.POLICY
    return MaintenancePolicyRead(
        version=p.version,
        estado=p.estado,
        procedencia=p.procedencia,
        proximo_km=p.proximo_km,
        proximo_km_por_tipo=p.proximo_km_por_tipo,
    )


@router.get("/maintenance/alerts", response_model=list[MaintenanceRead])
def list_maintenance_alerts(db: Session = Depends(get_db)) -> list[MaintenanceRead]:
    """RF-13: mantenimientos pendientes ya vencidos o próximos a vencer por
    kilometraje, del más urgente al menos urgente."""
    rows = (
        db.query(MaintenanceRecord, Vehicle.current_mileage_km)
        .join(Vehicle, Vehicle.id == MaintenanceRecord.vehicle_id)
        .filter(MaintenanceRecord.status == "pendiente", MaintenanceRecord.scheduled_mileage_km.isnot(None))
        .all()
    )
    alerts = [_read_with_urgency(record, current_km) for record, current_km in rows]
    alerts = [a for a in alerts if a.urgency in (policy.VENCIDO, policy.PROXIMO)]
    alerts.sort(key=lambda a: (a.urgency != policy.VENCIDO, a.km_remaining))
    return alerts
