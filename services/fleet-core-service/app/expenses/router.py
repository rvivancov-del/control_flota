"""Gastos operativos de un viaje: combustible, peajes y alimentación
(RF-08, RF-09, RF-10), anidados bajo /trips/{trip_id}, y su consulta global
filtrada por vehículo, conductor, tipo o rango de fechas (RF-14)."""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ROLES_OPERATIVOS, require_role
from app.expenses.schemas import (
    ALLOWED_TYPES,
    ExpenseCreate,
    ExpenseListRead,
    ExpenseRead,
    ExpenseUpdate,
)
from app.models.expense import Expense
from app.models.trip import Trip

router = APIRouter(
    prefix="/trips/{trip_id}/expenses",
    tags=["expenses"],
    dependencies=[Depends(require_role(*ROLES_OPERATIVOS))],
)

# RF-14: consulta transversal (todos los viajes), separada del router anidado.
query_router = APIRouter(
    prefix="/expenses",
    tags=["expenses"],
    dependencies=[Depends(require_role(*ROLES_OPERATIVOS))],
)


def _get_trip_or_404(trip_id: uuid.UUID, db: Session) -> Trip:
    """Resuelve el viaje padre o corta con 404 -- todo gasto cuelga de un viaje."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado.")
    return trip


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    trip_id: uuid.UUID, payload: ExpenseCreate, db: Session = Depends(get_db)
) -> ExpenseRead:
    """RF-08, RF-09, RF-10: combustible, peajes y alimentación asociados a un viaje."""
    _get_trip_or_404(trip_id, db)

    expense = Expense(trip_id=trip_id, **payload.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return ExpenseRead.model_validate(expense)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    trip_id: uuid.UUID, expense_id: uuid.UUID, payload: ExpenseUpdate, db: Session = Depends(get_db)
) -> ExpenseRead:
    """Corrige un gasto ya registrado — por ejemplo, añadir los litros de una
    carga de combustible que se registró sin ese dato."""
    _get_trip_or_404(trip_id, db)
    expense = db.get(Expense, expense_id)
    if expense is None or expense.trip_id != trip_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto no encontrado.")
    changes = payload.model_dump(exclude_unset=True)
    if "location" in changes:
        if expense.type != "peaje":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La ubicación solo aplica a los gastos de peaje.",
            )
        if changes["location"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La ubicación de un peaje no puede quedar vacía.",
            )
    for field, value in changes.items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return ExpenseRead.model_validate(expense)


@router.get("", response_model=list[ExpenseRead])
def list_expenses(trip_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ExpenseRead]:
    """Lista los gastos de un viaje, ordenados por fecha."""
    _get_trip_or_404(trip_id, db)
    expenses = (
        db.query(Expense)
        .filter(Expense.trip_id == trip_id)
        .order_by(Expense.expense_date)
        .all()
    )
    return [ExpenseRead.model_validate(e) for e in expenses]


@query_router.get("", response_model=list[ExpenseListRead])
def query_expenses(
    vehicle_id: Optional[uuid.UUID] = None,
    driver_id: Optional[uuid.UUID] = None,
    type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[ExpenseListRead]:
    """RF-14: gastos de todos los viajes, filtrados por vehículo, conductor, tipo o
    rango de fechas (por fecha del gasto), del más reciente al más antiguo."""
    if type is not None and type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"type debe ser uno de: {', '.join(sorted(ALLOWED_TYPES))}",
        )
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from no puede ser posterior a date_to.",
        )
    query = db.query(Expense, Trip).join(Trip, Expense.trip_id == Trip.id)
    if vehicle_id is not None:
        query = query.filter(Trip.vehicle_id == vehicle_id)
    if driver_id is not None:
        query = query.filter(Trip.driver_id == driver_id)
    if type is not None:
        query = query.filter(Expense.type == type)
    if date_from is not None:
        query = query.filter(Expense.expense_date >= date_from)
    if date_to is not None:
        query = query.filter(Expense.expense_date <= date_to)
    rows = query.order_by(Expense.expense_date.desc(), Expense.created_at.desc()).limit(limit).all()
    return [
        ExpenseListRead(
            **ExpenseRead.model_validate(expense).model_dump(),
            vehicle_id=trip.vehicle_id,
            driver_id=trip.driver_id,
            origin=trip.origin,
            destination=trip.destination,
        )
        for expense, trip in rows
    ]
