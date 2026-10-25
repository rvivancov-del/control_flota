"""Bloqueo temporal de cuentas por intentos fallidos (RNF-03).

Tras MAX_FAILED_ATTEMPTS contraseñas incorrectas seguidas la cuenta queda bloqueada
LOCKOUT_MINUTES minutos (aunque la contraseña sea correcta durante ese lapso); pasado el
plazo se desbloquea sola, y un administrador puede desbloquearla antes. El bloqueo es
distinto de desactivar la cuenta (`is_active`), que solo hace un administrador. Así un
atacante no puede dejar fuera a un usuario para siempre, y el único administrador no puede
quedar bloqueado sin recuperación.
"""
import os
from datetime import datetime, timedelta


def _env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} debe ser un entero, se recibió {raw!r}") from None
    if not low <= value <= high:
        raise ValueError(f"{name}={value} fuera de [{low}, {high}]")
    return value


MAX_FAILED_ATTEMPTS = _env_int("LOGIN_MAX_FAILED_ATTEMPTS", 5, 3, 20)
LOCKOUT_MINUTES = _env_int("LOGIN_LOCKOUT_MINUTES", 15, 1, 1440)


def is_locked(user, now: datetime) -> bool:
    return user.locked_until is not None and user.locked_until > now


def register_failure(user, now: datetime) -> bool:
    """Cuenta una contraseña incorrecta. Devuelve True si este fallo bloqueó la cuenta
    (el contador vuelve a cero para que, al vencer el bloqueo, haya un intento nuevo completo)."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
        user.failed_login_attempts = 0
        return True
    return False


def clear(user) -> None:
    """Un inicio de sesión correcto, o un desbloqueo del administrador, borra el estado de bloqueo."""
    user.failed_login_attempts = 0
    user.locked_until = None
