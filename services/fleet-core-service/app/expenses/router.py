"""Gastos operativos de un viaje: combustible, peajes y alimentación
(RF-08, RF-09, RF-10) -- siempre anidados bajo /trips/{trip_id}."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ROLES_OPERATIVOS, require_role
from app.expenses.schemas import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.models.expense import Expense
from app.models.trip import Trip

router = APIRouter(
    prefix="/trips/{trip_id}/expenses",
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
    for field, value in payload.model_dump(exclude_unset=True).items():
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
