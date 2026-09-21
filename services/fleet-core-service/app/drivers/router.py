"""CRUD de conductores (RF-05) y gestión de su credencial de código QR (RF-18).

RF-03: cualquier rol operativo consulta conductores; solo admin los da de alta,
los edita y emite, rota o revoca su credencial de despacho."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ADMIN, ROLES_OPERATIVOS, require_role
from app.despacho import qr_token
from app.drivers.schemas import DriverCreate, DriverQrIssued, DriverRead, DriverUpdate
from app.models.driver import Driver

router = APIRouter(
    prefix="/drivers", tags=["drivers"], dependencies=[Depends(require_role(*ROLES_OPERATIVOS))]
)
_solo_admin = [Depends(require_role(ADMIN))]


def _issued(driver: Driver, token: str, response: Response) -> DriverQrIssued:
    """Respuesta que lleva el token en claro: nunca debe quedar en caché."""
    response.headers["Cache-Control"] = "no-store"
    return DriverQrIssued(**DriverRead.model_validate(driver).model_dump(), qr_token=token)


@router.post(
    "", response_model=DriverQrIssued, status_code=status.HTTP_201_CREATED, dependencies=_solo_admin
)
def create_driver(
    payload: DriverCreate, response: Response, db: Session = Depends(get_db)
) -> DriverQrIssued:
    """RF-05: alta de conductores. RF-18: cada conductor recibe una credencial
    personal para su código QR de despacho; el token en claro se devuelve solo
    en esta respuesta (en la base queda únicamente su hash)."""
    if db.query(Driver).filter(Driver.license_number == payload.license_number).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un conductor con ese número de licencia.",
        )
    driver = Driver(**payload.model_dump())
    token = qr_token.issue(driver)
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return _issued(driver, token, response)


@router.post(
    "/{driver_id}/regenerate-qr", response_model=DriverQrIssued, dependencies=_solo_admin
)
def regenerate_qr_token(
    driver_id: uuid.UUID, response: Response, db: Session = Depends(get_db)
) -> DriverQrIssued:
    """Rota la credencial: invalida el código QR impreso anteriormente (por
    ejemplo, si se perdió la tarjeta de cabina) y emite uno nuevo con su
    vigencia completa. El token nuevo se muestra solo en esta respuesta."""
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")
    token = qr_token.issue(driver)
    db.commit()
    db.refresh(driver)
    return _issued(driver, token, response)


@router.post("/{driver_id}/revoke-qr", response_model=DriverRead, dependencies=_solo_admin)
def revoke_qr_token(driver_id: uuid.UUID, db: Session = Depends(get_db)) -> DriverRead:
    """RF-18: revoca la credencial sin emitir otra; el conductor no podrá
    despachar por QR hasta que se le genere un código nuevo."""
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")
    qr_token.revoke(driver)
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


@router.patch("/{driver_id}", response_model=DriverRead, dependencies=_solo_admin)
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
