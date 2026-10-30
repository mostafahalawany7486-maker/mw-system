"""Rent Billing Engine: extend Invoice and Receipt (no new tables)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-19

Per the pre-implementation analysis: this spec's "Rent Invoice" (a
billing document, issued before payment, with a full status lifecycle)
and "Payment Receipt" (generated only after payment) map directly onto
the *existing* `Invoice` and `Receipt` models — Invoice already has
issue_date/due_date/invoice_status and a working payment-recording flow
(`record_invoice_payment`); Receipt is already auto-issued after every
tenant/owner payment. Creating new "RentInvoice"/"RentReceipt" tables
would duplicate both. Everything below is additive.

Note on invoice numbering: the spec's example format ("RR-2026-000001")
suggests a year-scoped sequence. The existing `invoice_number` sequence
(`INV-000001`, global, not year-scoped) is already used throughout
Phases 8-13 and by every existing invoice in this system. Changing its
format would break backward compatibility for data that already exists,
which the spec itself requires preserving. The existing format and
column are kept unchanged; see docs/rent-billing-engine.md for the full
reasoning.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------- Invoice: status lifecycle, snapshot, billing cycle, void/print tracking ----------------
    op.add_column("invoices", sa.Column("billing_cycle", sa.String(20), nullable=True))
    op.add_column("invoices", sa.Column("billing_period_start", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("billing_period_end", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("snapshot", sa.JSON(), nullable=True))
    op.add_column("invoices", sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("invoices", sa.Column("void_reason", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("print_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("invoices", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("qr_token", sa.String(36), nullable=True))
    op.create_index("ix_invoices_qr_token", "invoices", ["qr_token"], unique=True)
    op.create_index("ix_invoices_billing_period_end", "invoices", ["billing_period_end"])

    # ---------------- Receipt: link back to the invoice it paid, print tracking ----------------
    op.add_column("receipts", sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True))
    op.add_column("receipts", sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("receipts", sa.Column("print_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_receipts_invoice_id", "receipts", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_receipts_invoice_id", table_name="receipts")
    op.drop_column("receipts", "print_count")
    op.drop_column("receipts", "printed_at")
    op.drop_column("receipts", "invoice_id")

    op.drop_index("ix_invoices_billing_period_end", table_name="invoices")
    op.drop_index("ix_invoices_qr_token", table_name="invoices")
    op.drop_column("invoices", "qr_token")
    op.drop_column("invoices", "delivered_at")
    op.drop_column("invoices", "print_count")
    op.drop_column("invoices", "printed_at")
    op.drop_column("invoices", "voided_at")
    op.drop_column("invoices", "void_reason")
    op.drop_column("invoices", "amount_paid")
    op.drop_column("invoices", "snapshot")
    op.drop_column("invoices", "billing_period_end")
    op.drop_column("invoices", "billing_period_start")
    op.drop_column("invoices", "billing_cycle")
