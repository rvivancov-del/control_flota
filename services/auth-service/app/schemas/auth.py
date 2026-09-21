"""Esquemas de request/response del flujo de login."""
from pydantic import BaseModel, field_validator

from app.schemas.user import UserRead, _validate_password_complexity


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _new_password_complexity(cls, value: str) -> str:
        return _validate_password_complexity(value)
