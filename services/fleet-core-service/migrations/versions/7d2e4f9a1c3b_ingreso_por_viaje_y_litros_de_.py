"""ingreso por viaje (revenue) y litros de combustible (liters)

Revision ID: 7d2e4f9a1c3b
Revises: 4bca723e1de3
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d2e4f9a1c3b'
down_revision: Union[str, None] = '4bca723e1de3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('revenue', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('expenses', sa.Column('liters', sa.Numeric(precision=8, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('expenses', 'liters')
    op.drop_column('trips', 'revenue')
