"""CRUD de conductores (RF-05), gestión de su credencial de código QR (RF-18) y
derechos sobre sus datos personales (RNF-11, LOPDP): rectificación y supresión.

RF-03: cualquier rol operativo consulta conductores; solo admin los da de alta,
los edita, los anonimiza y emite, rota o revoca su credencial de despacho."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import ADMIN, ROLES_OPERATIVOS, require_role
from app.despacho import qr_token
from app.drivers.licenses import LICENSE_TYPES
from app.drivers.schemas import (
    DriverCreate,
    DriverQrIssued,
    DriverRead,
    DriverUpdate,
    LicenseTypeRead,
)
from app.models.driver import Driver
from app.models.trip import Trip
from app.models.vehicle import Vehicle

router = APIRouter(
    prefix="/drivers", tags=["drivers"], dependencies=[Depends(require_role(*ROLES_OPERATIVOS))]
)
_solo_admin = [Depends(require_role(ADMIN))]


def _get_or_404(driver_id: uuid.UUID, db: Session) -> Driver:
    driver = db.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conductor no encontrado.")
    return driver


def _not_anonymized(driver: Driver) -> Driver:
    if driver.anonymized_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Los datos de este conductor fueron suprimidos y ya no se pueden modificar.",
        )
    return driver


def _check_vehicle_exists(vehicle_id: uuid.UUID | None, db: Session) -> None:
    if vehicle_id is not None and db.get(Vehicle, vehicle_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El vehículo indicado no existe."
        )


def _check_license_free(license_number: str, db: Session, own_id: uuid.UUID | None = None) -> None:
    other = db.query(Driver).filter(Driver.license_number == license_number).first()
    if other is not None and other.id != own_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un conductor con ese número de licencia.",
        )


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
    _check_license_free(payload.license_number, db)
    _check_vehicle_exists(payload.assigned_vehicle_id, db)
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
    driver = _not_anonymized(_get_or_404(driver_id, db))
    token = qr_token.issue(driver)
    db.commit()
    db.refresh(driver)
    return _issued(driver, token, response)


@router.post("/{driver_id}/revoke-qr", response_model=DriverRead, dependencies=_solo_admin)
def revoke_qr_token(driver_id: uuid.UUID, db: Session = Depends(get_db)) -> DriverRead:
    """RF-18: revoca la credencial sin emitir otra; el conductor no podrá
    despachar por QR hasta que se le genere un código nuevo."""
    driver = _get_or_404(driver_id, db)
    qr_token.revoke(driver)
    db.commit()
    db.refresh(driver)
    return DriverRead.model_validate(driver)


@router.get("/license-types", response_model=list[LicenseTypeRead])
def list_license_types() -> list[LicenseTypeRead]:
    """RF-05: tipos de licencia vigentes en Ecuador (ANT) que acepta el sistema."""
    return [LicenseTypeRead(code=code, description=text) for code, text in LICENSE_TYPES.items()]


@router.get("", response_model=list[DriverRead])
def list_drivers(db: Session = Depends(get_db)) -> list[DriverRead]:
    """Lista todos los conductores, ordenados por nombre."""
    drivers = db.query(Driver).order_by(Driver.full_name).all()
    return [DriverRead.model_validate(d) for d in drivers]


@router.get("/{driver_id}", response_model=DriverRead)
def get_driver(driver_id: uuid.UUID, db: Session = Depends(get_db)) -> DriverRead:
    """Consulta un conductor por id."""
    return DriverRead.model_validate(_get_or_404(driver_id, db))


@router.patch("/{driver_id}", response_model=DriverRead, dependencies=_solo_admin)
def update_driver(
    driver_id: uuid.UUID, payload: DriverUpdate, db: Session = Depends(get_db)
) -> DriverRead:
    """RF-05: edición de conductores. RNF-11: también la licencia, para rectificar datos."""
    driver = _not_anonymized(_get_or_404(driver_id, db))
    changes = payload.model_dump(exclude_unset=True)
    if "license_number" in changes:
        _check_license_free(changes["license_number"], db, own_id=driver.id)
    if "assigned_vehicle_id" in changes:
        _check_vehicle_exists(changes["assigned_vehicle_id"], db)
    for field, value in changes.items():
        setattr(driver, field, value)

    db.commit()
    db.refresh(driver)
    return DriverRead.model_validate(driver)


@router.post("/{driver_id}/anonymize", response_model=DriverRead, dependencies=_solo_admin)
def anonymize_driver(driver_id: uuid.UUID, db: Session = Depends(get_db)) -> DriverRead:
    """RNF-11 (LOPDP, derecho de supresión): borra los datos personales del conductor
    (nombre, licencia, teléfono, credencial de despacho) y lo deja inactivo. Los viajes y
    gastos se conservan como historial contable, ya sin identificar a la persona.
    Es irreversible; se rechaza si el conductor tiene viajes planificados o en curso."""
    driver = _get_or_404(driver_id, db)
    if driver.anonymized_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Los datos de este conductor ya fueron suprimidos."
        )
    open_trips = (
        db.query(Trip)
        .filter(Trip.driver_id == driver.id, Trip.status.in_(("planificado", "en_curso")))
        .count()
    )
    if open_trips:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El conductor tiene {open_trips} viaje(s) planificado(s) o en curso: ciérrelos o anúlelos antes de suprimir sus datos.",
        )
    suffix = driver.id.hex[:8]
    driver.full_name = f"Conductor anonimizado {suffix}"
    driver.license_number = f"ANON-{suffix}"
    driver.license_type = None
    driver.phone = None
    driver.status = "inactivo"
    driver.assigned_vehicle_id = None
    qr_token.revoke(driver)
    driver.anonymized_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(driver)
    return DriverRead.model_validate(driver)
