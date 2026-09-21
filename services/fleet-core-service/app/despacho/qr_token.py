"""Credencial personal del portal de despacho por QR (RF-18).

El token del código QR es una capacidad "bearer": quien lo presenta puede
registrar viajes a nombre del conductor. Un QR fijo pegado en la cabina se
escanea en cada viaje, así que no puede ser de un solo uso; en su lugar la
credencial es personal, revocable y con vigencia:

- Se generan 192 bits aleatorios (`secrets.token_urlsafe(24)`). Con esa
  entropía basta un SHA-256 sin sal ni estiramiento: no hay diccionario
  que atacar. En la base solo se guarda el hash, de modo que una filtración
  de la tabla no entrega credenciales utilizables.
- La comparación es en tiempo constante (`hmac.compare_digest`) y responde
  igual (401) si el conductor no existe, el token es falso, venció o fue
  revocado.
- Vence a los `QR_TOKEN_TTL_DAYS` días (180 por defecto) y se puede revocar
  o rotar en cualquier momento; el token en claro se muestra una sola vez,
  al emitirlo.
- Viaja en la cabecera `X-Despacho-Token` (no en la URL de la API) para que
  no quede en los registros de acceso del gateway.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

TOKEN_HEADER = "X-Despacho-Token"
_MAX_TOKEN_LENGTH = 128  # un token emitido mide 32 caracteres; lo demás es basura
_DEFAULT_TTL_DAYS = 180
# Se compara contra este valor cuando el conductor no tiene credencial, para
# que el tiempo de respuesta no distinga "sin credencial" de "credencial errónea".
_NO_CREDENTIAL = "0" * 64


def load_ttl_days() -> int:
    """Vigencia en días de una credencial recién emitida (QR_TOKEN_TTL_DAYS)."""
    raw = os.getenv("QR_TOKEN_TTL_DAYS", str(_DEFAULT_TTL_DAYS))
    try:
        days = int(raw)
    except ValueError:
        raise ValueError(f"QR_TOKEN_TTL_DAYS debe ser un entero de días, se recibió {raw!r}")
    if not 1 <= days <= 3650:
        raise ValueError(f"QR_TOKEN_TTL_DAYS={days} fuera de [1, 3650]")
    return days


TTL_DAYS = load_ttl_days()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(driver, now: Optional[datetime] = None) -> str:
    """Emite una credencial nueva para el conductor (invalida la anterior) y
    devuelve el token en claro: es la única vez que existe fuera del QR."""
    now = now or datetime.now(timezone.utc)
    token = secrets.token_urlsafe(24)
    driver.qr_token_hash = hash_token(token)
    driver.qr_token_issued_at = now
    driver.qr_token_expires_at = now + timedelta(days=TTL_DAYS)
    driver.qr_token_last_used_at = None
    return token


def revoke(driver) -> None:
    """Deja al conductor sin credencial: ningún QR impreso vuelve a funcionar."""
    driver.qr_token_hash = None
    driver.qr_token_issued_at = None
    driver.qr_token_expires_at = None
    driver.qr_token_last_used_at = None


def is_valid(driver, presented: Optional[str], now: Optional[datetime] = None) -> bool:
    """True si el token presentado corresponde a la credencial vigente del
    conductor. `driver` puede ser None (id inexistente): se responde igual."""
    now = now or datetime.now(timezone.utc)
    if not presented or len(presented) > _MAX_TOKEN_LENGTH:
        return False
    stored = getattr(driver, "qr_token_hash", None)
    coincide = hmac.compare_digest(hash_token(presented), stored or _NO_CREDENTIAL)
    expires = getattr(driver, "qr_token_expires_at", None)
    return bool(stored) and coincide and expires is not None and expires > now
