"""Modelo ORM de la tabla auth.users."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, false, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    """Usuario del sistema (Lámina D-01, tabla users). RF-01, RF-02, RF-03."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    # RNF-03: bloqueo temporal tras 5 intentos fallidos consecutivos (ver core/lockout.py).
    # No es lo mismo que is_active=False, que solo decide un administrador.
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    # RNF-02: obliga a cambiar la contraseña en el próximo inicio de sesión (p. ej. la
    # clave inicial del administrador sembrada en producción, o una asignada por otro admin).
    must_change_password = Column(Boolean, nullable=False, default=False, server_default=false())
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role = relationship("Role")
