"""Phase 14: Rent Cycle Engine

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-21

Adds two new tables only. Does NOT modify rental_contracts,
lease_agreements, invoices, or rental_payment_installments — the Rent
Cycle Engine references those tables read-only via foreign keys on the
new rent_cycle_records table (see app/models/rent_cycle.py for the full
design note).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
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
        "rent_cycles",
        *_audit_columns(),
        sa.Column("cycle_number", sa.String(20), nullable=False, unique=True),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("cycle_status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("property_ids", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rent_cycles_uuid", "rent_cycles", ["uuid"])
    op.create_index("ix_rent_cycles_cycle_number", "rent_cycles", ["cycle_number"])
    op.create_index("ix_rent_cycles_year", "rent_cycles", ["year"])
    op.create_index("ix_rent_cycles_cycle_status", "rent_cycles", ["cycle_status"])

    op.create_table(
        "rent_cycle_records",
        *_audit_columns(),
        sa.Column("cycle_id", sa.Integer(), sa.ForeignKey("rent_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("installment_id", sa.Integer(), sa.ForeignKey("rental_payment_installments.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("record_status", sa.String(20), nullable=False, server_default="generated"),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("cycle_id", "rental_contract_id", name="uq_rent_cycle_record_cycle_contract"),
    )
    op.create_index("ix_rent_cycle_records_uuid", "rent_cycle_records", ["uuid"])
    op.create_index("ix_rent_cycle_records_cycle_id", "rent_cycle_records", ["cycle_id"])
    op.create_index("ix_rent_cycle_records_rental_contract_id", "rent_cycle_records", ["rental_contract_id"])
    op.create_index("ix_rent_cycle_records_record_status", "rent_cycle_records", ["record_status"])


def downgrade() -> None:
    op.drop_table("rent_cycle_records")
    op.drop_table("rent_cycles")
