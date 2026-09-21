"""qr de despacho: token guardado como hash, con vigencia y ultimo uso (RF-18)

El token en claro (drivers.qr_token) se reemplaza por su SHA-256. Los QR ya
impresos siguen funcionando: el portal calcula el hash del token que recibe
y lo compara con el guardado, que aqui se rellena a partir del token en
claro existente. A esos QR se les da la vigencia estandar (QR_TOKEN_TTL_DAYS,
180 dias por defecto) contada desde esta migracion.

Revision ID: c3a7e15b9d20
Revises: 9f1a2b3c4d5e
Create Date: 2026-09-21 00:00:00.000000

"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a7e15b9d20'
down_revision: Union[str, None] = '9f1a2b3c4d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ttl_days() -> int:
    days = int(os.getenv("QR_TOKEN_TTL_DAYS", "180"))
    if not 1 <= days <= 3650:
        raise ValueError(f"QR_TOKEN_TTL_DAYS={days} fuera de [1, 3650]")
    return days


def upgrade() -> None:
    op.add_column('drivers', sa.Column('qr_token_hash', sa.String(64), nullable=True))
    op.add_column('drivers', sa.Column('qr_token_issued_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('drivers', sa.Column('qr_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('drivers', sa.Column('qr_token_last_used_at', sa.DateTime(timezone=True), nullable=True))

    # Mismo resultado que hashlib.sha256(token.encode("utf-8")).hexdigest().
    op.execute(
        sa.text(
            "UPDATE drivers "
            "SET qr_token_hash = encode(sha256(convert_to(qr_token, 'UTF8')), 'hex'), "
            "    qr_token_issued_at = now(), "
            "    qr_token_expires_at = now() + make_interval(days => :ttl) "
            "WHERE qr_token IS NOT NULL"
        ).bindparams(ttl=_ttl_days())
    )

    op.create_unique_constraint('uq_drivers_qr_token_hash', 'drivers', ['qr_token_hash'])
    op.drop_constraint('uq_drivers_qr_token', 'drivers', type_='unique')
    op.drop_column('drivers', 'qr_token')


def downgrade() -> None:
    # El hash es de un solo sentido: no se puede reconstruir el token en
    # claro. Al volver atras los conductores quedan sin token y hay que
    # regenerar su QR.
    op.add_column('drivers', sa.Column('qr_token', sa.String(64), nullable=True))
    op.create_unique_constraint('uq_drivers_qr_token', 'drivers', ['qr_token'])
    op.drop_constraint('uq_drivers_qr_token_hash', 'drivers', type_='unique')
    op.drop_column('drivers', 'qr_token_last_used_at')
    op.drop_column('drivers', 'qr_token_expires_at')
    op.drop_column('drivers', 'qr_token_issued_at')
    op.drop_column('drivers', 'qr_token_hash')
