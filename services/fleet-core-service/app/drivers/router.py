"""CRUD de conductores (RF-05) y gestión de su token de código QR (RF-18)."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.drivers.schemas import DriverCreate, DriverRead, DriverUpdate
from app.models.driver import Driver

router = APIRouter(
    prefix="/drivers", tags=["drivers"], dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db)) -> DriverRead:
    """RF-05: alta de conductores. RF-18: cada conductor recibe un token
    opaco para su código QR de despacho — no es una contraseña que el
    conductor recuerde, es una capacidad que el QR ya lleva incorporada."""
    if db.query(Driver).filter(Driver.license_number == payload.license_number).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un conductor con ese número de licencia.",
        )
    driver = Driver(**payload.model_dump(), qr_token=secrets.token_urlsafe(24))
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return DriverRead.model_validate(driver)


@router.post("/{driver_id}/regenerate-qr", response_model=DriverRead)
def regenerate_qr_token(driver_id: uuid.UUID, db: Session = Depends(get_db)) -> DriverRead:
    """Invalida el código QR impreso anteriormente (por ejemplo, si se
    perdió la tarjeta de cabina) y emite uno nuevo."""
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")
    driver.qr_token = secrets.token_urlsafe(24)
    db.commit()
    db.refresh(driver)
    return DriverRead.model_validate(driver)


@router.get("", response_model=list[DriverRead])
def list_drivers(db: Session = Depends(get_db)) -> list[DriverRead]:
    """Lista todos los conductores, ordenados por nombre."""
    drivers = db.query(Driver).order_by(Driver.full_name).all()
    return [DriverRead.model_validate(d) for d in drivers]


@router.get("/{driver_id}", response_model=DriverRead)
def get_driver(driver_id: uuid.UUID, db: Session = Depends(get_db)) -> DriverRead:
    """Consulta un conductor por id."""
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")
    return DriverRead.model_validate(driver)


@router.patch("/{driver_id}", response_model=DriverRead)
def update_driver(
    driver_id: uuid.UUID, payload: DriverUpdate, db: Session = Depends(get_db)
) -> DriverRead:
    """RF-05: edición de conductores."""
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(driver, field, value)

    db.commit()
    db.refresh(driver)
    return DriverRead.model_validate(driver)
