"""bloqueo temporal de cuentas (RNF-03) y cambio obligatorio de contrasena (RNF-02)

- users.locked_until: fin del bloqueo temporal por intentos fallidos (NULL = sin bloqueo).
- users.must_change_password: fuerza el cambio de contrasena en el proximo inicio de sesion.
- users.password_changed_at: cuando se cambio la contrasena por ultima vez (NULL = nunca, la inicial).

Las cuentas ya desactivadas por el bloqueo permanente anterior siguen inactivas: un administrador
puede reactivarlas desde la lista de usuarios.

Revision ID: f2c8a5d1b7e3
Revises: 2c937ee4c54f
Create Date: 2026-09-21 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c8a5d1b7e3'
down_revision: Union[str, None] = '2c937ee4c54f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'locked_until')
