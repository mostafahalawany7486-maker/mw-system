"""Add auto_renew to rental_contracts

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-29

Confirmed directly: tenant rental contracts specifically (not Master
Leases with owners) should be able to renew themselves automatically
with no reminder notification, per-contract rather than a global
switch. Defaults to false — every existing contract keeps today's
manual-renewal-with-reminder behavior unless explicitly turned on.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rental_contracts", sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("rental_contracts", "auto_renew")
