"""Dependencias de autenticación y autorización de reporting-service.

Igual que en fleet-core-service, no hay tabla de usuarios propia: el JWT se
decodifica localmente. La diferencia es que aquí se guarda también el token
crudo, porque este servicio debe reenviarlo tal cual a fleet-core-service en
cada llamada interna (ver core/fleet_client.py) -- fleet-core-service es
quien realmente valida el token contra los datos que sirve, en vez de que
reporting-service reimplemente esa verificación por su cuenta.

RF-03: `admin` y `operador` consultan el tablero y los reportes en pantalla;
solo `admin` exporta reportes (Excel/PDF)."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import JWTError, decode_access_token

ADMIN = "admin"
OPERADOR = "operador"
# Lista explícita: un rol nuevo no hereda acceso por omisión.
ROLES_OPERATIVOS = (ADMIN, OPERADOR)

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass
class CurrentUser:
    """Identidad del JWT, incluido el token crudo para reenviar por HTTP."""

    id: str
    role: str
    token: str  # se reenvía tal cual a fleet-core-service


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    """Decodifica el JWT del header Authorization; no consulta base de datos."""
    try:
        payload = decode_access_token(credentials.credentials)
        return CurrentUser(id=payload["sub"], role=payload["role"], token=credentials.credentials)
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )


def require_role(*allowed_roles: str):
    """RF-03: restringe un router o endpoint a uno o más roles (403 si el rol
    del JWT no está permitido). Un token ausente o inválido responde 401
    antes de evaluar el rol."""

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta operación.",
            )
        return current_user

    return _dependency
