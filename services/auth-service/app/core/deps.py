"""Dependencias de autenticación/autorización compartidas por los routers:
validar el JWT de cada request (get_current_user) y restringir endpoints a
roles específicos (require_role)."""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import JWTError, decode_access_token
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decodifica el JWT del header Authorization y carga el usuario activo.

    Se usa como dependencia en cualquier endpoint que exija sesión iniciada.
    """
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        ) from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inválido o inactivo.",
        )
    return user


def require_role(*allowed_roles: str):
    """RF-03: restringe un router/endpoint a uno o más roles. RNF-02: quien debe cambiar su
    contraseña solo puede usar /me y /change-password (que usan get_current_user, no esto)."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.must_change_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debe cambiar su contraseña antes de continuar.",
            )
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta operación.",
            )
        return current_user

    return _dependency
