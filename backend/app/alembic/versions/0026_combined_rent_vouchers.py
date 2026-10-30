"""Combined Rent Vouchers — multiple months' transactions on one voucher

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-23

Two additive nullable columns on the existing `rent_vouchers` table
only — no new table, no change to any existing column or the existing
UniqueConstraint(transaction_id, copy_type). See
app/models/rent_voucher.py for the full design rationale.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rent_vouchers", sa.Column("extra_transaction_ids", sa.Text(), nullable=True))
    op.add_column("rent_vouchers", sa.Column("combined_amount", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("rent_vouchers", "combined_amount")
    op.drop_column("rent_vouchers", "extra_transaction_ids")
