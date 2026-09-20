"""Esquemas de usuarios: alta, edición y lectura -- incluye la regla de
complejidad de contraseña (RNF-02)."""
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.role import RoleRead

_PASSWORD_RULE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


def _validate_password_complexity(password: str) -> str:
    """RNF-02: exige al menos 8 caracteres con letras y números."""
    if not _PASSWORD_RULE.match(password):
        raise ValueError(
            "La contraseña debe tener al menos 8 caracteres, con letras y números."
        )
    return password


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role_id: uuid.UUID

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, value: str) -> str:
        return _validate_password_complexity(value)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _validate_password_complexity(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: Optional[str]
    is_active: bool
    role: RoleRead
    created_at: Optional[datetime]
