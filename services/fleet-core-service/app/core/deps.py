"""Dependencias de autenticación y autorización de fleet-core-service.

A diferencia de auth-service, aquí no hay tabla de usuarios propia (cada
microservicio es dueño exclusivo de su esquema) -- el JWT ya trae el id y
el rol del usuario, así que basta con decodificarlo, sin ir a la base de
datos. Consecuencia declarada: un cambio de rol o una baja de usuario en
auth-service se refleja aquí cuando el JWT vigente (60 min) expira.

RF-03: matriz de permisos por rol. `admin` administra el catálogo
(vehículos, conductores y el QR de despacho); `operador` opera el día a día
(viajes, gastos, mantenimientos) y consulta todo lo demás."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import JWTError, decode_access_token

ADMIN = "admin"
OPERADOR = "operador"
# Roles con acceso a la operación de la flota. Se listan de forma explícita
# (en vez de aceptar "cualquier JWT válido") para que un rol nuevo no herede
# acceso por omisión.
ROLES_OPERATIVOS = (ADMIN, OPERADOR)

_bearer_scheme = HTTPBearer(auto_error=True)


@dataclass
class CurrentUser:
    """Identidad mínima extraída del JWT: sin fila propia en este servicio."""

    id: str
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    """Decodifica el JWT del header Authorization; no consulta base de datos."""
    try:
        payload = decode_access_token(credentials.credentials)
        user = CurrentUser(id=payload["sub"], role=payload["role"])
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        ) from None
    # RNF-02: auth-service marca con `mcp` el token de quien debe cambiar su contraseña; hasta
    # que la cambie (y reciba un token nuevo) no puede usar este servicio.
    if payload.get("mcp"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe cambiar su contraseña antes de continuar.",
        )
    return user


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
