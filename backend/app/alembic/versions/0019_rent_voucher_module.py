"""Phase 15: Rent Voucher Printing module

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-21

Adds one new table only. Does NOT modify transactions, tenants,
properties, or rental_payment_installments — RentVoucher references
transactions read-only via transaction_id (see
app/models/rent_voucher.py for the full design note). The existing
Rental Receipt Module (RentalPaymentInstallment.receipt_number etc.,
Phase 7) is completely untouched — this is a distinct document type,
not a replacement.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "rent_vouchers",
        *_audit_columns(),
        sa.Column("voucher_number", sa.String(20), nullable=False, unique=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("copy_type", sa.String(10), nullable=False),
        sa.Column("rental_month", sa.Date(), nullable=False),
        sa.Column("barcode_value", sa.String(100), nullable=False, unique=True),
        sa.Column("print_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("transaction_id", "copy_type", name="uq_rent_voucher_transaction_copy"),
    )
    op.create_index("ix_rent_vouchers_uuid", "rent_vouchers", ["uuid"])
    op.create_index("ix_rent_vouchers_voucher_number", "rent_vouchers", ["voucher_number"])
    op.create_index("ix_rent_vouchers_transaction_id", "rent_vouchers", ["transaction_id"])
    op.create_index("ix_rent_vouchers_copy_type", "rent_vouchers", ["copy_type"])
    op.create_index("ix_rent_vouchers_barcode_value", "rent_vouchers", ["barcode_value"])


def downgrade() -> None:
    op.drop_table("rent_vouchers")
