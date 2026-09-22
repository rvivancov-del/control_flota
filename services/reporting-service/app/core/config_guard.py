"""Guardia de configuración (RNF-02): el servicio se niega a arrancar con secretos de
desarrollo fuera de un entorno de desarrollo.

`APP_ENV` decide el modo. Si no está definida se asume producción (seguro por omisión); los
archivos `.env.example` de este repositorio la fijan en `development` para el uso local.
En producción, arrancar con la clave JWT o la contraseña de la base de datos por defecto
(o con una clave JWT demasiado corta) es un error de configuración, no una advertencia.

Este archivo es idéntico en auth-service, fleet-core-service y reporting-service (los servicios no
comparten código en tiempo de ejecución); scripts/check_shared_code.py verifica que no se separen.
"""
import os

DEFAULT_SECRET = "changeme_local_only"
MIN_JWT_SECRET_LENGTH = 32
_DEVELOPMENT_NAMES = {"development", "dev", "local", "test"}


def environment() -> str:
    return os.getenv("APP_ENV", "production").strip().lower()


def is_development() -> bool:
    return environment() in _DEVELOPMENT_NAMES


def insecure_settings(extra_secrets: dict[str, str] | None = None, uses_database: bool = True) -> list[str]:
    """Lista de problemas de configuración (vacía si es segura o si es desarrollo).
    `extra_secrets` nombra variables adicionales que no pueden quedar en su valor por defecto;
    `uses_database` es False en el servicio que no se conecta a PostgreSQL (reporting)."""
    if is_development():
        return []
    problems = []
    jwt_secret = os.getenv("JWT_SECRET_KEY", DEFAULT_SECRET)
    if jwt_secret == DEFAULT_SECRET:
        problems.append("JWT_SECRET_KEY tiene el valor por defecto de desarrollo")
    elif len(jwt_secret) < MIN_JWT_SECRET_LENGTH:
        problems.append(f"JWT_SECRET_KEY es demasiado corta (mínimo {MIN_JWT_SECRET_LENGTH} caracteres)")
    if uses_database and os.getenv("POSTGRES_PASSWORD", DEFAULT_SECRET) == DEFAULT_SECRET:
        problems.append("POSTGRES_PASSWORD tiene el valor por defecto de desarrollo")
    for name, default in (extra_secrets or {}).items():
        if os.getenv(name, default) == default:
            problems.append(f"{name} tiene el valor por defecto de desarrollo")
    return problems


def assert_secure_configuration(
    service: str, extra_secrets: dict[str, str] | None = None, uses_database: bool = True
) -> None:
    """Detiene el arranque si la configuración es insegura para el entorno actual."""
    problems = insecure_settings(extra_secrets, uses_database)
    if problems:
        raise RuntimeError(
            f"{service}: configuración insegura para APP_ENV={environment()!r}: "
            + "; ".join(problems)
            + ". Defina secretos reales o use APP_ENV=development solo en un equipo local."
        )
