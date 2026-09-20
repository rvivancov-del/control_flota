"""Endpoints de agregación SQL consumidos internamente por reporting-service
(no por el frontend) para construir el dashboard sin traer fila por fila."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics.schemas import (
    ExpenseAggregateRow,
    MaintenanceAggregateRow,
    RouteAggregateRow,
    TripAggregateRow,
)
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.expense import Expense
from app.models.maintenance import MaintenanceRecord
from app.models.trip import Trip

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])

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
    query = db.query(
        Trip.vehicle_id,
        Trip.driver_id,
        trip_date,
        func.count(Trip.id).label("trip_count"),
        distance,
        max_mileage,
        revenue,
    ).filter(Trip.status == "completado")
    if date_from is not None:
        query = query.filter(func.date(Trip.departure_at) >= date_from)
    if date_to is not None:
        query = query.filter(func.date(Trip.departure_at) <= date_to)
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
    cost_query = (
        db.query(
            Trip.origin,
            Trip.destination,
            func.sum(Expense.amount).label("cost_total"),
        )
        .join(Expense, Expense.trip_id == Trip.id)
        .filter(Trip.status == "completado")
    )
    if date_from is not None:
        trip_query = trip_query.filter(func.date(Trip.departure_at) >= date_from)
        cost_query = cost_query.filter(func.date(Trip.departure_at) >= date_from)
    if date_to is not None:
        trip_query = trip_query.filter(func.date(Trip.departure_at) <= date_to)
        cost_query = cost_query.filter(func.date(Trip.departure_at) <= date_to)

    trip_rows = trip_query.group_by(Trip.origin, Trip.destination).all()
    cost_by_route = {
        (r.origin, r.destination): r.cost_total
        for r in cost_query.group_by(Trip.origin, Trip.destination).all()
    }

    return [
        RouteAggregateRow(
            origin=r.origin,
            destination=r.destination,
            trip_count=r.trip_count,
            avg_distance_km=round(r.avg_distance_km or 0),
            cost_total=cost_by_route.get((r.origin, r.destination), 0),
        )
        for r in trip_rows
    ]


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
