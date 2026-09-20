"""Endpoints de sesión: login (emite JWT) y /me (usuario autenticado actual)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserRead


# Sin prefijo propio: el gateway ya expone este servicio bajo /api/auth/ y
# reescribe la ruta antes de reenviarla (ver infra/nginx/nginx.conf), así que
# aquí las rutas son relativas a la raíz del servicio (/login, no /auth/login).
router = APIRouter(tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
_INVALID_CREDENTIALS_MSG = "Usuario o contraseña inválidos, o cuenta inactiva."


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """RF-02: autenticación con JWT. RNF-03: bloquea la cuenta tras 5 fallos."""
    user = db.query(User).filter(User.username == payload.username).first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MSG
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_MSG
        )

    user.failed_login_attempts = 0
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), role=user.role.name)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Devuelve el usuario dueño del token enviado (para refrescar la sesión en el frontend)."""
    return UserRead.model_validate(current_user)
