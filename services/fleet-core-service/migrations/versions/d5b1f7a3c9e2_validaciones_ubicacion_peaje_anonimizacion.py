"""validaciones de dominio (CHECK), ubicacion del peaje (RF-09) y anonimizacion de conductores (RNF-11)

- expenses.location: ubicacion del peaje (nullable: los peajes historicos no la tienen).
- drivers.anonymized_at: marca la supresion de datos personales (LOPDP).
- drivers.license_type se normaliza ('Tipo E' -> 'E', '' -> NULL, D1/E1 -> D/E segun la
  Resolucion 028-DE-ANT-2021) y se restringe a los tipos vigentes.
- CHECK de estados de vehiculos y conductores.
Si quedan valores que no encajan, la migracion se detiene y los lista (no se pierde nada en silencio).

Revision ID: d5b1f7a3c9e2
Revises: c3a7e15b9d20
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5b1f7a3c9e2'
down_revision: Union[str, None] = 'c3a7e15b9d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LICENSE_TYPES = ("A", "A1", "B", "C", "C1", "D", "E", "F", "G")
DRIVER_STATUS = ("activo", "inactivo")
VEHICLE_STATUS = ("activo", "mantenimiento", "inactivo")


def _in_list(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _fail_on_leftovers(conn, table: str, column: str, allowed, nullable: bool) -> None:
    where = f"{column} IS NOT NULL AND " if nullable else ""
    rows = conn.execute(
        sa.text(f"SELECT DISTINCT {column} FROM {table} WHERE {where}{column} NOT IN ({_in_list(allowed)})")
    ).fetchall()
    if rows:
        raise RuntimeError(
            f"{table}.{column} tiene valores fuera del conjunto permitido {tuple(allowed)}: "
            f"{[r[0] for r in rows]}. Corrijalos y vuelva a ejecutar la migracion."
        )


def upgrade() -> None:
    op.add_column('expenses', sa.Column('location', sa.String(120), nullable=True))
    op.add_column('drivers', sa.Column('anonymized_at', sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            r"UPDATE drivers SET license_type = "
            r"NULLIF(replace(regexp_replace(upper(trim(license_type)), '^(TIPO|LICENCIA)\s+', ''), ' ', ''), '') "
            r"WHERE license_type IS NOT NULL"
        )
    )
    conn.execute(sa.text("UPDATE drivers SET license_type = 'D' WHERE license_type = 'D1'"))
    conn.execute(sa.text("UPDATE drivers SET license_type = 'E' WHERE license_type = 'E1'"))

    _fail_on_leftovers(conn, "drivers", "license_type", LICENSE_TYPES, nullable=True)
    _fail_on_leftovers(conn, "drivers", "status", DRIVER_STATUS, nullable=False)
    _fail_on_leftovers(conn, "vehicles", "status", VEHICLE_STATUS, nullable=False)

    op.create_check_constraint(
        'ck_drivers_license_type', 'drivers', f"license_type IS NULL OR license_type IN ({_in_list(LICENSE_TYPES)})"
    )
    op.create_check_constraint('ck_drivers_status', 'drivers', f"status IN ({_in_list(DRIVER_STATUS)})")
    op.create_check_constraint('ck_vehicles_status', 'vehicles', f"status IN ({_in_list(VEHICLE_STATUS)})")
    op.create_check_constraint('ck_expenses_location_only_toll', 'expenses', "location IS NULL OR type = 'peaje'")


def downgrade() -> None:
    op.drop_constraint('ck_expenses_location_only_toll', 'expenses', type_='check')
    op.drop_constraint('ck_vehicles_status', 'vehicles', type_='check')
    op.drop_constraint('ck_drivers_status', 'drivers', type_='check')
    op.drop_constraint('ck_drivers_license_type', 'drivers', type_='check')
    op.drop_column('drivers', 'anonymized_at')
    op.drop_column('expenses', 'location')
