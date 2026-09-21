"""Ciclo de vida de un viaje: crear, listar/filtrar, iniciar, cerrar,
anular y corregir el ingreso (RF-06, RF-07, RF-13, RF-14)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.maintenance import policy
from app.models.driver import Driver
from app.models.maintenance import MaintenanceRecord
from app.models.trip import Trip
from app.models.vehicle import Vehicle
from app.trips.schemas import (
    MaintenanceAlertBrief,
    TripClose,
    TripCloseResult,
    TripCreate,
    TripRead,
    TripRevenueUpdate,
)

router = APIRouter(prefix="/trips", tags=["trips"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TripRead:
    """RF-06: registro de viajes. Estado inicial "planificado" (Lámina D-05)."""
    if db.get(Vehicle, payload.vehicle_id) is None:
        raise HTTPException(status_code=422, detail="El vehículo indicado no existe.")
    if db.get(Driver, payload.driver_id) is None:
        raise HTTPException(status_code=422, detail="El conductor indicado no existe.")

    trip = Trip(
        **payload.model_dump(),
        created_by=uuid.UUID(current_user.id),
        status="planificado",
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return TripRead.model_validate(trip)


@router.get("", response_model=list[TripRead])
def list_trips(
    vehicle_id: uuid.UUID | None = None,
    driver_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> list[TripRead]:
    """RF-14: consulta y filtrado de viajes por vehículo, conductor o estado."""
    query = db.query(Trip)
    if vehicle_id is not None:
        query = query.filter(Trip.vehicle_id == vehicle_id)
    if driver_id is not None:
        query = query.filter(Trip.driver_id == driver_id)
    if status_filter is not None:
        query = query.filter(Trip.status == status_filter)
    trips = query.order_by(Trip.departure_at.desc()).all()
    return [TripRead.model_validate(t) for t in trips]


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: uuid.UUID, db: Session = Depends(get_db)) -> TripRead:
    """Consulta un viaje por id."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado.")
    return TripRead.model_validate(trip)


@router.patch("/{trip_id}/start", response_model=TripRead)
def start_trip(trip_id: uuid.UUID, db: Session = Depends(get_db)) -> TripRead:
    """Transición planificado -> en_curso (Lámina D-05)."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado.")
    if trip.status != "planificado":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede iniciar un viaje en estado '{trip.status}'.",
        )
    trip.status = "en_curso"
    db.commit()
    db.refresh(trip)
    return TripRead.model_validate(trip)


@router.patch("/{trip_id}/cancel", response_model=TripRead)
def cancel_trip(trip_id: uuid.UUID, db: Session = Depends(get_db)) -> TripRead:
    """Transición planificado|en_curso -> anulado (Lámina D-05)."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado.")
    if trip.status not in ("planificado", "en_curso"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede anular un viaje en estado '{trip.status}'.",
        )
    trip.status = "anulado"
    db.commit()
    db.refresh(trip)
    return TripRead.model_validate(trip)


@router.patch("/{trip_id}/revenue", response_model=TripRead)
def set_trip_revenue(
    trip_id: uuid.UUID, payload: TripRevenueUpdate, db: Session = Depends(get_db)
) -> TripRead:
    """Registra o corrige el ingreso (flete) de un viaje ya cerrado — el pago
    del cliente a veces se confirma días después de la entrega."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado.")
    trip.revenue = payload.revenue
    db.commit()
    db.refresh(trip)
    return TripRead.model_validate(trip)


@router.patch("/{trip_id}/close", response_model=TripCloseResult)
def close_trip(
    trip_id: uuid.UUID, payload: TripClose, db: Session = Depends(get_db)
) -> TripCloseResult:
    """RF-07 + RF-13 (Láminas D-03 y D-06): cierra el viaje, actualiza el
    kilometraje del vehículo y evalúa qué mantenimientos quedaron vencidos o
    próximos a vencer por kilometraje (política en app/maintenance/policy.py)."""
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado.")
    if trip.status != "en_curso":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede cerrar un viaje en estado '{trip.status}'.",
        )
    if payload.end_mileage_km < trip.start_mileage_km:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El kilometraje final no puede ser menor al inicial.",
        )

    trip.end_mileage_km = payload.end_mileage_km
    trip.arrival_at = payload.arrival_at
    trip.revenue = payload.revenue
    trip.status = "completado"

    vehicle = db.get(Vehicle, trip.vehicle_id)
    vehicle.current_mileage_km = payload.end_mileage_km

    pending = (
        db.query(MaintenanceRecord)
        .filter(
            MaintenanceRecord.vehicle_id == vehicle.id,
            MaintenanceRecord.status == "pendiente",
            MaintenanceRecord.scheduled_mileage_km.isnot(None),
        )
        .all()
    )
    alerts = []
    for record in pending:
        remaining, urgency = policy.assess(record, vehicle.current_mileage_km)
        if urgency in (policy.VENCIDO, policy.PROXIMO):
            brief = MaintenanceAlertBrief.model_validate(record)
            brief.km_remaining, brief.urgency = remaining, urgency
            alerts.append(brief)
    alerts.sort(key=lambda a: (a.urgency != policy.VENCIDO, a.km_remaining))

    db.commit()
    db.refresh(trip)

    return TripCloseResult(
        trip=TripRead.model_validate(trip),
        maintenance_alerts=alerts,
    )
