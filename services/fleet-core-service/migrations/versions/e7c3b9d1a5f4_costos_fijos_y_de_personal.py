"""costos fijos por vehiculo y costos de personal por conductor (Fase 3)

Tablas nuevas para calcular el costo total Ct = Cv + Cf (Poliak et al., 2025) y el costo por
kilometro en las categorias de Zysinska & Menes (2026): depreciacion, capital, seguros,
impuestos y personal. Los montos son mensuales o anuales con vigencia y se prorratean por dias.

Revision ID: e7c3b9d1a5f4
Revises: d5b1f7a3c9e2
Create Date: 2026-09-21 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e7c3b9d1a5f4'
down_revision: Union[str, None] = 'd5b1f7a3c9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fixed_costs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vehicles.id'), nullable=False),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('period', sa.String(10), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint('amount > 0', name='ck_fixed_costs_amount_positive'),
        sa.CheckConstraint("category IN ('depreciacion', 'capital', 'seguro', 'impuestos', 'otros')", name='ck_fixed_costs_category'),
        sa.CheckConstraint("period IN ('mensual', 'anual')", name='ck_fixed_costs_period'),
        sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name='ck_fixed_costs_validity'),
    )
    op.create_index('ix_fixed_costs_vehicle_id', 'fixed_costs', ['vehicle_id'])

    op.create_table(
        'personnel_costs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('driver_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('drivers.id'), nullable=False),
        sa.Column('concept', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.CheckConstraint('amount > 0', name='ck_personnel_costs_amount_positive'),
        sa.CheckConstraint("concept IN ('sueldo', 'beneficios_sociales', 'otros')", name='ck_personnel_costs_concept'),
        sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name='ck_personnel_costs_validity'),
    )
    op.create_index('ix_personnel_costs_driver_id', 'personnel_costs', ['driver_id'])


def downgrade() -> None:
    op.drop_index('ix_personnel_costs_driver_id', table_name='personnel_costs')
    op.drop_table('personnel_costs')
    op.drop_index('ix_fixed_costs_vehicle_id', table_name='fixed_costs')
    op.drop_table('fixed_costs')
