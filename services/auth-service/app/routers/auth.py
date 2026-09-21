"""Endpoints de sesión: login (emite JWT), /me (usuario autenticado actual) y
/change-password (cambio de contraseña, obligatorio cuando el usuario lo tiene pendiente)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import lockout
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, Token
from app.schemas.user import UserRead


# Sin prefijo propio: el gateway ya expone este servicio bajo /api/auth/ y
# reescribe la ruta antes de reenviarla (ver infra/nginx/nginx.conf), así que
# aquí las rutas son relativas a la raíz del servicio (/login, no /auth/login).
router = APIRouter(tags=["auth"])

# Un mismo mensaje para usuario inexistente, contraseña errónea, cuenta inactiva o bloqueada:
# no revela cuál de esos casos ocurrió (no permite descubrir qué usuarios existen).
_INVALID_CREDENTIALS_MSG = "Usuario o contraseña inválidos, o cuenta inactiva o bloqueada temporalmente."
# Hash de una contraseña cualquiera: se verifica contra él cuando el usuario no existe, para que
# el tiempo de respuesta no delate si el usuario existe.
_UNKNOWN_USER_HASH = hash_password("contraseña-que-nadie-usa")


def _issue_token(user: User) -> Token:
    token = create_access_token(
        subject=str(user.id), role=user.role.name, must_change_password=user.must_change_password
    )
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """RF-02: autenticación con JWT. RNF-03: tras 5 contraseñas incorrectas seguidas la cuenta
    se bloquea unos minutos (core/lockout.py); durante el bloqueo ni la contraseña correcta entra."""
    now = datetime.now(timezone.utc)
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None:
        verify_password(payload.password, _UNKNOWN_USER_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MSG)
    if not user.is_active or lockout.is_locked(user, now):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MSG)

    if not verify_password(payload.password, user.password_hash):
        lockout.register_failure(user, now)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MSG)

    lockout.clear(user)
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Devuelve el usuario dueño del token enviado (para refrescar la sesión en el frontend)."""
    return UserRead.model_validate(current_user)


@router.post("/change-password", response_model=Token)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Token:
    """RNF-02: cambia la contraseña del usuario en sesión y devuelve un token nuevo (sin la
    marca de cambio pendiente). Exige la contraseña actual; equivocarse cuenta como intento
    fallido, igual que en el login, para que un token robado no sirva para adivinarla."""
    now = datetime.now(timezone.utc)
    if lockout.is_locked(current_user, now):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MSG)
    if not verify_password(payload.current_password, current_user.password_hash):
        lockout.register_failure(current_user, now)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="La contraseña actual no es correcta."
        )
    if verify_password(payload.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La contraseña nueva debe ser distinta de la actual.",
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    current_user.password_changed_at = now
    lockout.clear(current_user)
    db.commit()
    db.refresh(current_user)
    return _issue_token(current_user)
