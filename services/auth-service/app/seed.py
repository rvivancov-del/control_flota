"""Seed idempotente: roles fijos (admin, operador) + un usuario administrador
inicial, para poder autenticarse la primera vez. Se ejecuta en cada arranque
del contenedor (ver Dockerfile) — no crea nada si ya existe.
"""

import os

from app.core import config_guard
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User

DEFAULT_ROLES = ["admin", "operador"]
DEFAULT_ADMIN_PASSWORD = "Admin1234"


def _seed_roles(db) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name in DEFAULT_ROLES:
        role = db.query(Role).filter(Role.name == name).first()
        if role is None:
            role = Role(name=name)
            db.add(role)
            db.flush()
        roles[name] = role
    return roles


def _seed_admin_user(db, admin_role: Role) -> None:
    username = os.getenv("ADMIN_USERNAME", "admin")
    if db.query(User).filter(User.username == username).first():
        return
    password = os.getenv("ADMIN_INITIAL_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    # RNF-02: fuera de desarrollo no se siembra el administrador con la clave publicada en la
    # documentación, y la clave inicial que sí se use debe cambiarse en el primer ingreso.
    if not config_guard.is_development() and password == DEFAULT_ADMIN_PASSWORD:
        raise RuntimeError(
            f"auth-service: ADMIN_INITIAL_PASSWORD tiene el valor por defecto y APP_ENV={config_guard.environment()!r}: "
            "defina una contraseña inicial propia para el administrador."
        )
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name="Administrador",
        role_id=admin_role.id,
        must_change_password=not config_guard.is_development(),
    )
    db.add(user)


def main() -> None:
    db = SessionLocal()
    try:
        roles = _seed_roles(db)
        _seed_admin_user(db, roles["admin"])
        db.commit()
        print("[seed] roles y usuario admin verificados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
