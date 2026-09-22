"""Endpoints de agregación SQL consumidos internamente por reporting-service
(no por el frontend) para construir el dashboard sin traer fila por fila."""
from datetime import date
from typing import Optional

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    ExpenseAggregateRow,
    MaintenanceAggregateRow,
    RouteAggregateRow,
    TripAggregateRow,
)
from app.core.database import get_db
from app.core.dates import filter_utc_days
from app.core.deps import ADMIN, ROLES_OPERATIVOS, require_role
from app.costs import proration
from app.costs.schemas import FixedCostAccrualRow, PersonnelCostAccrualRow
from app.models.costs import FixedCost, PersonnelCost
from app.models.expense import Expense
from app.models.maintenance import MaintenanceRecord
from app.models.trip import Trip

router = APIRouter(
    prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_role(*ROLES_OPERATIVOS))]
)

# Estos tres endpoints existen para que reporting-service deje de traer cada
# viaje y cada gasto por HTTP y sumarlos en Python (N llamadas por N filas):
# la base de datos ya sabe sumar — un año de historia son unas pocas
# consultas SQL con GROUP BY, no miles de peticiones.


@router.get("/expenses", response_model=list[ExpenseAggregateRow])
def expense_aggregate(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
) -> list[ExpenseAggregateRow]:
    """Gastos agrupados por vehículo, conductor, fecha y tipo (SUM/COUNT en SQL)."""
    query = (
        db.query(
            Trip.vehicle_id,
            Trip.driver_id,
            Expense.expense_date,
            Expense.type,
            func.sum(Expense.amount).label("amount_total"),
            func.coalesce(func.sum(Expense.liters), 0).label("liters_total"),
            func.count(Expense.id).label("count"),
        )
        .join(Trip, Expense.trip_id == Trip.id)
        .filter(Trip.status == "completado")
    )
    if date_from is not None:
        query = query.filter(Expense.expense_date >= date_from)
    if date_to is not None:
        query = query.filter(Expense.expense_date <= date_to)
    rows = query.group_by(Trip.vehicle_id, Trip.driver_id, Expense.expense_date, Expense.type).all()
    return [
        ExpenseAggregateRow(
            vehicle_id=r.vehicle_id,
            driver_id=r.driver_id,
            expense_date=r.expense_date,
            type=r.type,
            amount_total=r.amount_total,
            liters_total=r.liters_total,
            count=r.count,
        )
        for r in rows
    ]


@router.get("/trips", response_model=list[TripAggregateRow])
def trip_aggregate(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
) -> list[TripAggregateRow]:
    """Viajes agrupados por vehículo, conductor y fecha: conteo, distancia e ingreso."""
    trip_date = func.date(Trip.departure_at).label("trip_date")
    distance = func.sum(Trip.end_mileage_km - Trip.start_mileage_km).label("distance_km")
    max_mileage = func.max(Trip.end_mileage_km).label("end_mileage_km")
    revenue = func.coalesce(func.sum(Trip.revenue), 0).label("revenue_total")
    revenue_trips = func.count(Trip.revenue).label("revenue_trip_count")
    revenue_distance = func.coalesce(
        func.sum(case((Trip.revenue.isnot(None), Trip.end_mileage_km - Trip.start_mileage_km), else_=0)), 0
    ).label("revenue_distance_km")
    query = db.query(
        Trip.vehicle_id,
        Trip.driver_id,
        trip_date,
        func.count(Trip.id).label("trip_count"),
        distance,
        max_mileage,
        revenue,
        revenue_trips,
        revenue_distance,
    ).filter(Trip.status == "completado")
    query = filter_utc_days(query, Trip.departure_at, date_from, date_to)
    rows = query.group_by(Trip.vehicle_id, Trip.driver_id, trip_date).all()
    return [
        TripAggregateRow(
            vehicle_id=r.vehicle_id,
            driver_id=r.driver_id,
            trip_date=r.trip_date,
            trip_count=r.trip_count,
            distance_km=r.distance_km or 0,
            end_mileage_km=r.end_mileage_km or 0,
            revenue_total=r.revenue_total,
            revenue_trip_count=r.revenue_trip_count,
            revenue_distance_km=r.revenue_distance_km,
        )
        for r in rows
    ]


@router.get("/routes", response_model=list[RouteAggregateRow])
def route_aggregate(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
) -> list[RouteAggregateRow]:
    """Costo y distancia promedio por ruta — contexto para juzgar si un
    conductor caro lo es por su manejo o por las rutas que le tocan.

    Dos consultas separadas (no un join trips-expenses) a propósito: un
    join directo multiplicaría cada viaje por su número de gastos y sesgaría
    el promedio de distancia hacia los viajes con más gastos registrados."""
    trip_query = db.query(
        Trip.origin,
        Trip.destination,
        func.count(Trip.id).label("trip_count"),
        func.avg(Trip.end_mileage_km - Trip.start_mileage_km).label("avg_distance_km"),
    ).filter(Trip.status == "completado")
    def _by_type(kind: str):
        return func.coalesce(func.sum(case((Expense.type == kind, Expense.amount), else_=0)), 0).label(f"cost_{kind}")

    cost_query = (
        db.query(
            Trip.origin,
            Trip.destination,
            func.sum(Expense.amount).label("cost_total"),
            _by_type("combustible"),
            _by_type("peaje"),
            _by_type("alimentacion"),
        )
        .join(Expense, Expense.trip_id == Trip.id)
        .filter(Trip.status == "completado")
    )
    trip_query = filter_utc_days(trip_query, Trip.departure_at, date_from, date_to)
    cost_query = filter_utc_days(cost_query, Trip.departure_at, date_from, date_to)

    trip_rows = trip_query.group_by(Trip.origin, Trip.destination).all()
    cost_by_route = {(r.origin, r.destination): r for r in cost_query.group_by(Trip.origin, Trip.destination).all()}

    routes = []
    for r in trip_rows:
        cost = cost_by_route.get((r.origin, r.destination))
        routes.append(
            RouteAggregateRow(
                origin=r.origin,
                destination=r.destination,
                trip_count=r.trip_count,
                avg_distance_km=round(r.avg_distance_km or 0),
                cost_total=cost.cost_total if cost else 0,
                cost_combustible=cost.cost_combustible if cost else 0,
                cost_peaje=cost.cost_peaje if cost else 0,
                cost_alimentacion=cost.cost_alimentacion if cost else 0,
            )
        )
    return routes


@router.get("/maintenance", response_model=list[MaintenanceAggregateRow])
def maintenance_aggregate(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
) -> list[MaintenanceAggregateRow]:
    """Mantenimientos completados y con costo, agrupados por vehículo/fecha/tipo."""
    query = db.query(
        MaintenanceRecord.vehicle_id,
        MaintenanceRecord.performed_at,
        MaintenanceRecord.category,
        MaintenanceRecord.maintenance_type,
        func.sum(MaintenanceRecord.cost).label("cost_total"),
        func.count(MaintenanceRecord.id).label("count"),
    ).filter(MaintenanceRecord.status == "completado", MaintenanceRecord.cost.isnot(None))
    if date_from is not None:
        query = query.filter(MaintenanceRecord.performed_at >= date_from)
    if date_to is not None:
        query = query.filter(MaintenanceRecord.performed_at <= date_to)
    rows = query.group_by(
        MaintenanceRecord.vehicle_id,
        MaintenanceRecord.performed_at,
        MaintenanceRecord.category,
        MaintenanceRecord.maintenance_type,
    ).all()
    return [
        MaintenanceAggregateRow(
            vehicle_id=r.vehicle_id,
            performed_at=r.performed_at,
            category=r.category,
            maintenance_type=r.maintenance_type,
            cost_total=r.cost_total,
            count=r.count,
        )
        for r in rows
    ]


def _require_period(date_from: Optional[date], date_to: Optional[date]) -> tuple[date, date]:
    """Los costos fijos se prorratean por días: sin un período completo no hay nada que devengar."""
    if date_from is None or date_to is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from y date_to son obligatorios para prorratear costos fijos.",
        )
    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from no puede ser posterior a date_to."
        )
    return date_from, date_to


@router.get(
    "/fixed-costs", response_model=list[FixedCostAccrualRow], dependencies=[Depends(require_role(ADMIN))]
)
def fixed_cost_accrual(
    date_from: Optional[date] = None, date_to: Optional[date] = None, db: Session = Depends(get_db)
) -> list[FixedCostAccrualRow]:
    """Costos fijos devengados en [date_from, date_to], por vehículo y categoría (solo admin).
    Cada costo se prorratea por los días de su vigencia que caen en el período (ver costs/proration.py)."""
    start, end = _require_period(date_from, date_to)
    totals: dict[tuple, Decimal] = {}
    for c in db.query(FixedCost).filter(
        FixedCost.valid_from <= end, (FixedCost.valid_to.is_(None)) | (FixedCost.valid_to >= start)
    ):
        amount = proration.accrued(c.amount, c.period, c.valid_from, c.valid_to, start, end)
        totals[(c.vehicle_id, c.category)] = totals.get((c.vehicle_id, c.category), Decimal(0)) + amount
    return [
        FixedCostAccrualRow(vehicle_id=vehicle_id, category=category, amount=proration.money(amount))
        for (vehicle_id, category), amount in sorted(totals.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))
    ]


@router.get(
    "/personnel-costs", response_model=list[PersonnelCostAccrualRow], dependencies=[Depends(require_role(ADMIN))]
)
def personnel_cost_accrual(
    date_from: Optional[date] = None, date_to: Optional[date] = None, db: Session = Depends(get_db)
) -> list[PersonnelCostAccrualRow]:
    """Costos de personal devengados en [date_from, date_to], por conductor y concepto (solo admin)."""
    start, end = _require_period(date_from, date_to)
    totals: dict[tuple, Decimal] = {}
    for c in db.query(PersonnelCost).filter(
        PersonnelCost.valid_from <= end, (PersonnelCost.valid_to.is_(None)) | (PersonnelCost.valid_to >= start)
    ):
        amount = proration.accrued(c.amount, "mensual", c.valid_from, c.valid_to, start, end)
        totals[(c.driver_id, c.concept)] = totals.get((c.driver_id, c.concept), Decimal(0)) + amount
    return [
        PersonnelCostAccrualRow(driver_id=driver_id, concept=concept, amount=proration.money(amount))
        for (driver_id, concept), amount in sorted(totals.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))
    ]
