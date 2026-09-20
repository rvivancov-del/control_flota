"""Dependencia de autenticación de fleet-core-service.

A diferencia de auth-service, aquí no hay tabla de usuarios propia (cada
microservicio es dueño exclusivo de su esquema) -- el JWT ya trae el id y
el rol del usuario, así que basta con decodificarlo, sin ir a la base de
datos."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import JWTError, decode_access_token

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
        return CurrentUser(id=payload["sub"], role=payload["role"])
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )
