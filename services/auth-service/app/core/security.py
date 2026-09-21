"""Primitivas de seguridad (RNF-02): hashing de contraseñas con bcrypt y
emisión/lectura de JWT (HS256) compartidos entre los tres microservicios."""
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme_local_only")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Aplica bcrypt a una contraseña en texto plano para guardarla en la BD."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Compara una contraseña en texto plano contra su hash bcrypt almacenado."""
    return _pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str, role: str, must_change_password: bool = False) -> str:
    """Emite un JWT firmado (sub=id de usuario, role, exp) válido por JWT_EXPIRE_MINUTES.
    Si el usuario debe cambiar su contraseña, el token lleva `mcp: true`: fleet-core y reporting
    (que no consultan la base de usuarios) lo rechazan hasta que se emita un token nuevo."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "role": role, "exp": expires_at}
    if must_change_password:
        payload["mcp"] = True
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Lanza jose.JWTError si el token es inválido o expiró."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "JWTError",
]
