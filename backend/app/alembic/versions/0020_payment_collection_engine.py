"""Phase 16: Payment & Collection Engine

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-21

Adds two new tables only. Does NOT modify tenants, properties,
rental_contracts, invoices, financial_accounts, or transactions —
Payment/PaymentAllocation reference them read-only (see
app/models/payment.py for the full design note).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0020"
down_revision: Union[str, None] = "0019"
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
        "payments",
        *_audit_columns(),
        sa.Column("payment_number", sa.String(20), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("rental_contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id"), nullable=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("financial_accounts.id"), nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("refund_reason", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_uuid", "payments", ["uuid"])
    op.create_index("ix_payments_payment_number", "payments", ["payment_number"])
    op.create_index("ix_payments_tenant_id", "payments", ["tenant_id"])
    op.create_index("ix_payments_rental_contract_id", "payments", ["rental_contract_id"])
    op.create_index("ix_payments_property_id", "payments", ["property_id"])
    op.create_index("ix_payments_reference_number", "payments", ["reference_number"])
    op.create_index("ix_payments_payment_status", "payments", ["payment_status"])

    op.create_table(
        "payment_allocations",
        *_audit_columns(),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_payment_invoice"),
    )
    op.create_index("ix_payment_allocations_uuid", "payment_allocations", ["uuid"])
    op.create_index("ix_payment_allocations_payment_id", "payment_allocations", ["payment_id"])
    op.create_index("ix_payment_allocations_invoice_id", "payment_allocations", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("payment_allocations")
    op.drop_table("payments")
