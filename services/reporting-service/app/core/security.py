"""Verificación de JWT en reporting-service (no emite tokens, solo los lee)."""
import os

from jose import JWTError, jwt

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme_local_only")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def decode_access_token(token: str) -> dict:
    """Verifica el JWT del usuario (emitido por auth-service, clave HS256
    compartida) antes de usarlo para consultar fleet-core-service."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


__all__ = ["decode_access_token", "JWTError"]
