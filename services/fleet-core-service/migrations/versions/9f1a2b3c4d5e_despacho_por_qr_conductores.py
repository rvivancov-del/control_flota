"""despacho por qr: conductores, vehiculo asignado, campos de viaje

Revision ID: 9f1a2b3c4d5e
Revises: 7d2e4f9a1c3b
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9f1a2b3c4d5e'
down_revision: Union[str, None] = '7d2e4f9a1c3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('drivers', sa.Column('status', sa.String(20), nullable=False, server_default='activo'))
    op.add_column('drivers', sa.Column('assigned_vehicle_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('drivers', sa.Column('qr_token', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_drivers_qr_token', 'drivers', ['qr_token'])
    op.create_foreign_key('fk_drivers_assigned_vehicle_id', 'drivers', 'vehicles', ['assigned_vehicle_id'], ['id'])

    op.add_column('vehicles', sa.Column('registration_number', sa.String(30), nullable=True))

    op.add_column('trips', sa.Column('remission_guide', sa.String(60), nullable=True))
    op.add_column('trips', sa.Column('cargo_type', sa.String(120), nullable=True))
    op.add_column('trips', sa.Column('notes', sa.String(500), nullable=True))
    op.alter_column('trips', 'created_by', nullable=True)


def downgrade() -> None:
    op.alter_column('trips', 'created_by', nullable=False)
    op.drop_column('trips', 'notes')
    op.drop_column('trips', 'cargo_type')
    op.drop_column('trips', 'remission_guide')

    op.drop_column('vehicles', 'registration_number')

    op.drop_constraint('fk_drivers_assigned_vehicle_id', 'drivers', type_='foreignkey')
    op.drop_constraint('uq_drivers_qr_token', 'drivers', type_='unique')
    op.drop_column('drivers', 'qr_token')
    op.drop_column('drivers', 'assigned_vehicle_id')
    op.drop_column('drivers', 'status')
