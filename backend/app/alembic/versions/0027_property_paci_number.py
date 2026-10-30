"""Add PACI address number to Property

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-24

One additive, nullable column on the existing `properties` table —
corrects an earlier mistake where the Rent Voucher print template
sourced "PACI Number" from Tenant.national_id (a personal ID) instead
of the unit's own official Kuwait PACI address code. See
docs/paci-number-correction.md.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("paci_number", sa.String(30), nullable=True))
    op.create_index("ix_properties_paci_number", "properties", ["paci_number"])


def downgrade() -> None:
    op.drop_index("ix_properties_paci_number", table_name="properties")
    op.drop_column("properties", "paci_number")
