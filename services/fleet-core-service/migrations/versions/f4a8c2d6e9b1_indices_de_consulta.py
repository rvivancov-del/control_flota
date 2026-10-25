"""indices de consulta sobre viajes, gastos y mantenimientos

Hasta ahora las unicas estructuras de acceso eran las claves primarias y las restricciones unicas: cada
consulta del tablero y cada filtro de RF-14 recorria la tabla completa. Los indices salen de las
consultas reales (analytics, listas filtradas, alertas) y se midieron en scripts/bench_queries.py con
10^3, 10^5 y 10^6 viajes; el informe esta en 12_RESULTADOS_OBTENIDOS/benchmark_consultas.md.

Revision ID: f4a8c2d6e9b1
Revises: e7c3b9d1a5f4
Create Date: 2026-09-22 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4a8c2d6e9b1'
down_revision: Union[str, None] = 'e7c3b9d1a5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_trips_departure_at', 'trips', ['departure_at'])
    op.create_index('ix_trips_vehicle_id_departure_at', 'trips', ['vehicle_id', 'departure_at'])
    op.create_index('ix_trips_driver_id', 'trips', ['driver_id'])
    op.create_index('ix_expenses_trip_id_expense_date', 'expenses', ['trip_id', 'expense_date'])
    op.create_index('ix_expenses_expense_date', 'expenses', ['expense_date'])
    op.create_index('ix_maintenance_records_vehicle_id_status', 'maintenance_records', ['vehicle_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_maintenance_records_vehicle_id_status', table_name='maintenance_records')
    op.drop_index('ix_expenses_expense_date', table_name='expenses')
    op.drop_index('ix_expenses_trip_id_expense_date', table_name='expenses')
    op.drop_index('ix_trips_driver_id', table_name='trips')
    op.drop_index('ix_trips_vehicle_id_departure_at', table_name='trips')
    op.drop_index('ix_trips_departure_at', table_name='trips')
