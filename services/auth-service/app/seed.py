"""Seed idempotente: roles fijos (admin, operador) + un usuario administrador
inicial, para poder autenticarse la primera vez. Se ejecuta en cada arranque
del contenedor (ver Dockerfile) — no crea nada si ya existe.
"""

import os

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User

DEFAULT_ROLES = ["admin", "operador"]


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
    password = os.getenv("ADMIN_INITIAL_PASSWORD", "Admin1234")
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name="Administrador",
        role_id=admin_role.id,
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
