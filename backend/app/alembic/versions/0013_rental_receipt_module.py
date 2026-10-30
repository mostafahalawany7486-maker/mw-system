"""Rental Receipt Module: receipt tracking on rental_payment_installments

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-18

Per Phase 1 analysis: rental_payment_installments is already the "one
row per contract per month" concept a Rental Receipt needs (due_date,
amount, contract -> tenant/property chain already exist). Rather than
create a new Receipt-like table (which would duplicate/confuse the
existing `receipts` table — a different, already-wired-up concept:
post-payment proof-of-payment, auto-issued by create_transaction()),
this migration adds exactly the columns that were genuinely missing:
a receipt number (separate sequence from RCP-/INV-/TXN-), and print
tracking for the audit trail. Everything else needed (tenant/property
data, amount, payment confirmation) already exists on this table or on
Transaction. Purely additive — no existing column touched.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rental_payment_installments", sa.Column("receipt_number", sa.String(20), nullable=True))
    op.create_index("ix_rental_payment_installments_receipt_number", "rental_payment_installments", ["receipt_number"], unique=True)
    op.add_column("rental_payment_installments", sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rental_payment_installments", sa.Column("print_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("rental_payment_installments", "print_count")
    op.drop_column("rental_payment_installments", "printed_at")
    op.drop_index("ix_rental_payment_installments_receipt_number", table_name="rental_payment_installments")
    op.drop_column("rental_payment_installments", "receipt_number")
