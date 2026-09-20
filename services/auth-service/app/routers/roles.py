"""Consulta de roles disponibles (admin, operador) para poblar el formulario
de alta/edición de usuarios en el frontend -- solo lectura, solo admin."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.role import Role
from app.schemas.role import RoleRead

router = APIRouter(
    prefix="/roles", tags=["roles"], dependencies=[Depends(require_role("admin"))]
)


@router.get("", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db)) -> list[RoleRead]:
    """Lista los roles disponibles (admin, operador)."""
    roles = db.query(Role).order_by(Role.name).all()
    return [RoleRead.model_validate(r) for r in roles]
