"""CRUD de usuarios (RF-01) -- todo el router exige rol admin."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import lockout
from app.core.database import get_db
from app.core.deps import require_role
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

# Un único callable para el router y para los endpoints que necesitan saber quién es el
# administrador en sesión: FastAPI lo resuelve una sola vez por petición.
_admin = require_role("admin")

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(_admin)])


def _ensure_an_admin_remains(db: Session, user: User, *, stays_admin: bool, stays_active: bool) -> None:
    """RNF-03: nunca puede quedar el sistema sin un administrador activo (si el único admin se
    desactivara o se degradara, nadie podría gestionar usuarios ni desbloquear cuentas)."""
    if user.role.name != "admin" or not user.is_active:
        return  # este usuario no cuenta como administrador activo hoy
    if stays_admin and stays_active:
        return
    others = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(Role.name == "admin", User.is_active.is_(True), User.id != user.id)
        .count()
    )
    if others == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Debe quedar al menos un administrador activo: cree o active otro antes de este cambio.",
        )


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    """RF-01: alta de usuarios con rol asignado."""
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El nombre de usuario ya existe."
        )

    role = db.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El rol indicado no existe."
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=payload.role_id,
        must_change_password=payload.must_change_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[UserRead]:
    """Lista todos los usuarios, ordenados por nombre de usuario."""
    users = db.query(User).order_by(User.username).all()
    return [UserRead.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserRead:
    """Consulta un usuario por id."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(_admin),
) -> UserRead:
    """RF-01: edición y desactivación de usuarios."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    new_role = user.role
    if payload.role_id is not None:
        new_role = db.get(Role, payload.role_id)
        if new_role is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El rol indicado no existe.",
            )
    _ensure_an_admin_remains(
        db,
        user,
        stays_admin=new_role.name == "admin",
        stays_active=user.is_active if payload.is_active is None else payload.is_active,
    )
    if payload.role_id is not None:
        user.role_id = payload.role_id

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.is_active is not None:
        user.is_active = payload.is_active
        if payload.is_active:
            # Reactivar una cuenta limpia también el bloqueo temporal y el contador de fallos.
            lockout.clear(user)

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        user.password_changed_at = datetime.now(timezone.utc)
        # Si otro administrador fija la contraseña, la conoce: el usuario debe cambiarla al ingresar
        # (salvo que el administrador se la cambie a sí mismo o indique lo contrario).
        if payload.must_change_password is None and user.id != current_admin.id:
            user.must_change_password = True
    if payload.must_change_password is not None:
        user.must_change_password = payload.must_change_password

    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/{user_id}/unlock", response_model=UserRead)
def unlock_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserRead:
    """RNF-03: quita el bloqueo temporal de una cuenta (por intentos fallidos) sin esperar a que
    venza. No reactiva una cuenta desactivada: eso se hace con PATCH is_active."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    lockout.clear(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)
