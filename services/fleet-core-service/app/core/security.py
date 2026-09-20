"""Verificación de JWT en fleet-core-service (no emite tokens, solo los lee)."""
import os

from jose import JWTError, jwt

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme_local_only")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def decode_access_token(token: str) -> dict:
    """Lanza jose.JWTError si el token es inválido o expiró.

    Verifica de forma independiente los JWT emitidos por auth-service: ambos
    servicios comparten JWT_SECRET_KEY (HS256, clave simétrica) para que cada
    uno valide tokens sin depender de una llamada de red al otro servicio.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


__all__ = ["decode_access_token", "JWTError"]
