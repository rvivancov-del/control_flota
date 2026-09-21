"""Costos fijos por vehículo y costos de personal por conductor (Fase 3).

Es información financiera (y, en el caso del personal, sueldos de personas): solo el rol
admin la consulta y la administra (RF-03). Los devengos por período que consume el
tablero están en /analytics/fixed-costs y /analytics/personnel-costs.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ADMIN, require_role
from app.costs.schemas import (
    FixedCostCreate,
    FixedCostRead,
    FixedCostUpdate,
    PersonnelCostCreate,
    PersonnelCostRead,
    PersonnelCostUpdate,
)
from app.models.costs import FixedCost, PersonnelCost
from app.models.driver import Driver
from app.models.vehicle import Vehicle

router = APIRouter(tags=["costs"], dependencies=[Depends(require_role(ADMIN))])


def _check_validity(record) -> None:
    if record.valid_to is not None and record.valid_to < record.valid_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha final de la vigencia no puede ser anterior a la inicial.",
        )


def _get_or_404(db: Session, model, record_id: uuid.UUID, label: str):
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} no encontrado.")
    return record


# ------------------------------------------------------------------ costos fijos por vehículo
@router.get("/fixed-costs", response_model=list[FixedCostRead])
def list_fixed_costs(vehicle_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)) -> list[FixedCostRead]:
    query = db.query(FixedCost)
    if vehicle_id is not None:
        query = query.filter(FixedCost.vehicle_id == vehicle_id)
    rows = query.order_by(FixedCost.vehicle_id, FixedCost.category, FixedCost.valid_from.desc()).all()
    return [FixedCostRead.model_validate(r) for r in rows]


@router.post("/fixed-costs", response_model=FixedCostRead, status_code=status.HTTP_201_CREATED)
def create_fixed_cost(payload: FixedCostCreate, db: Session = Depends(get_db)) -> FixedCostRead:
    if db.get(Vehicle, payload.vehicle_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El vehículo indicado no existe.")
    record = FixedCost(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return FixedCostRead.model_validate(record)


@router.patch("/fixed-costs/{cost_id}", response_model=FixedCostRead)
def update_fixed_cost(cost_id: uuid.UUID, payload: FixedCostUpdate, db: Session = Depends(get_db)) -> FixedCostRead:
    record = _get_or_404(db, FixedCost, cost_id, "Costo fijo")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    _check_validity(record)
    db.commit()
    db.refresh(record)
    return FixedCostRead.model_validate(record)


@router.delete("/fixed-costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fixed_cost(cost_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get_or_404(db, FixedCost, cost_id, "Costo fijo"))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ costos de personal por conductor
@router.get("/personnel-costs", response_model=list[PersonnelCostRead])
def list_personnel_costs(driver_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)) -> list[PersonnelCostRead]:
    query = db.query(PersonnelCost)
    if driver_id is not None:
        query = query.filter(PersonnelCost.driver_id == driver_id)
    rows = query.order_by(PersonnelCost.driver_id, PersonnelCost.concept, PersonnelCost.valid_from.desc()).all()
    return [PersonnelCostRead.model_validate(r) for r in rows]


@router.post("/personnel-costs", response_model=PersonnelCostRead, status_code=status.HTTP_201_CREATED)
def create_personnel_cost(payload: PersonnelCostCreate, db: Session = Depends(get_db)) -> PersonnelCostRead:
    driver = db.get(Driver, payload.driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El conductor indicado no existe.")
    if driver.anonymized_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Los datos de este conductor fueron suprimidos: no se le pueden registrar costos de personal.",
        )
    record = PersonnelCost(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return PersonnelCostRead.model_validate(record)


@router.patch("/personnel-costs/{cost_id}", response_model=PersonnelCostRead)
def update_personnel_cost(
    cost_id: uuid.UUID, payload: PersonnelCostUpdate, db: Session = Depends(get_db)
) -> PersonnelCostRead:
    record = _get_or_404(db, PersonnelCost, cost_id, "Costo de personal")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    _check_validity(record)
    db.commit()
    db.refresh(record)
    return PersonnelCostRead.model_validate(record)


@router.delete("/personnel-costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personnel_cost(cost_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get_or_404(db, PersonnelCost, cost_id, "Costo de personal"))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
