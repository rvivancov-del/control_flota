"""Portal de despacho por código QR (RF-18): permite a un conductor, sin
usuario ni contraseña, ver su vehículo asignado y registrar un viaje
directamente desde su celular escaneando el código de su cabina."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.despacho import qr_token
from app.despacho.schemas import DespachoCreate, DespachoInfo, DespachoResult, DespachoTripBrief
from app.models.driver import Driver
from app.models.expense import Expense
from app.models.trip import Trip
from app.models.vehicle import Vehicle

# Sin Depends(get_current_user): este router es la puerta de entrada para
# un conductor que solo tiene el código QR de su cabina, no una cuenta con
# usuario y contraseña. La credencial personal del conductor (token en la
# cabecera X-Despacho-Token, verificado contra su hash, con vigencia y
# revocable; ver qr_token.py) es, por diseño, el único control de acceso — RF-18.
router = APIRouter(prefix="/despacho", tags=["despacho"])


def _driver_por_token(driver_id: uuid.UUID, token: Optional[str], db: Session) -> Driver:
    """Valida la credencial del QR y que el conductor esté listo para despachar.
    Un conductor inexistente, un token falso, vencido o revocado responden lo
    mismo (401): el portal no revela cuál de esos casos ocurrió."""
    driver = db.get(Driver, driver_id)
    if not qr_token.is_valid(driver, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código QR inválido o vencido.")
    if driver.status != "activo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Este conductor no está activo.")
    if driver.assigned_vehicle_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Este conductor todavía no tiene un vehículo asignado.",
        )
    driver.qr_token_last_used_at = datetime.now(timezone.utc)
    db.commit()
    return driver


@router.get("/{driver_id}", response_model=DespachoInfo)
def get_despacho_info(
    driver_id: uuid.UUID,
    response: Response,
    x_despacho_token: Optional[str] = Header(default=None, alias=qr_token.TOKEN_HEADER),
    db: Session = Depends(get_db),
) -> DespachoInfo:
    """Datos del conductor y su vehículo asignado, para precargar el formulario del portal."""
    driver = _driver_por_token(driver_id, x_despacho_token, db)
    response.headers["Cache-Control"] = "no-store"
    vehicle = db.get(Vehicle, driver.assigned_vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo asignado no encontrado.")
    return DespachoInfo(
        driver_id=driver.id,
        driver_name=driver.full_name,
        driver_status=driver.status,
        vehicle_id=vehicle.id,
        vehicle_plate=vehicle.plate,
        vehicle_brand=vehicle.brand,
        vehicle_model=vehicle.model,
        vehicle_registration_number=vehicle.registration_number,
        vehicle_current_mileage_km=vehicle.current_mileage_km,
    )


@router.post("/{driver_id}", response_model=DespachoResult, status_code=status.HTTP_201_CREATED)
def create_despacho(
    driver_id: uuid.UUID,
    payload: DespachoCreate,
    x_despacho_token: Optional[str] = Header(default=None, alias=qr_token.TOKEN_HEADER),
    db: Session = Depends(get_db),
) -> DespachoResult:
    """RF-18: registra y arranca el viaje en un solo paso — el conductor no
    pasa por planificado -> iniciar como en el flujo de administración,
    porque para él el viaje ya está en curso en el momento en que sale."""
    driver = _driver_por_token(driver_id, x_despacho_token, db)
    vehicle = db.get(Vehicle, driver.assigned_vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehículo asignado no encontrado.")
    if payload.start_mileage_km < vehicle.current_mileage_km:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El kilometraje no puede ser menor al último registrado ({vehicle.current_mileage_km} km).",
        )

    departure_at = payload.departure_at or datetime.now(timezone.utc)
    trip = Trip(
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        created_by=None,
        origin=payload.origin,
        destination=payload.destination,
        departure_at=departure_at,
        start_mileage_km=payload.start_mileage_km,
        remission_guide=payload.remission_guide,
        cargo_type=payload.cargo_type,
        notes=payload.notes,
        status="en_curso",
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    if payload.fuel_amount is not None:
        expense = Expense(
            trip_id=trip.id,
            type="combustible",
            amount=payload.fuel_amount,
            liters=payload.fuel_liters,
            currency="USD",
            expense_date=departure_at.date(),
        )
        db.add(expense)
        db.commit()

    first_name = driver.full_name.split()[0]
    return DespachoResult(
        trip=DespachoTripBrief(
            id=trip.id, origin=trip.origin, destination=trip.destination,
            departure_at=trip.departure_at, status=trip.status,
        ),
        message=f"Viaje registrado con éxito. ¡Buen viaje, {first_name}!",
    )
