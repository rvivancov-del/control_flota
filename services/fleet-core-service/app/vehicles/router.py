"""CRUD de vehículos (RF-04)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ADMIN, ROLES_OPERATIVOS, require_role
from app.models.vehicle import Vehicle
from app.vehicles.schemas import VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter(
    prefix="/vehicles", tags=["vehicles"], dependencies=[Depends(require_role(*ROLES_OPERATIVOS))]
)


@router.post(
    "",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(ADMIN))],
)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)) -> VehicleRead:
    """RF-04: alta de vehículos (solo admin, RF-03)."""
    if db.query(Vehicle).filter(Vehicle.plate == payload.plate).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ya existe un vehículo con esa placa."
        )
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)


@router.get("", response_model=list[VehicleRead])
def list_vehicles(db: Session = Depends(get_db)) -> list[VehicleRead]:
    """Lista todos los vehículos, ordenados por placa."""
    vehicles = db.query(Vehicle).order_by(Vehicle.plate).all()
    return [VehicleRead.model_validate(v) for v in vehicles]


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: uuid.UUID, db: Session = Depends(get_db)) -> VehicleRead:
    """Consulta un vehículo por id."""
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado.")
    return VehicleRead.model_validate(vehicle)


@router.patch(
    "/{vehicle_id}", response_model=VehicleRead, dependencies=[Depends(require_role(ADMIN))]
)
def update_vehicle(
    vehicle_id: uuid.UUID, payload: VehicleUpdate, db: Session = Depends(get_db)
) -> VehicleRead:
    """RF-04: edición de vehículos (solo admin, RF-03)."""
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo no encontrado.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)
