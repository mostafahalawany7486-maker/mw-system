"""Phase 17: Owner Ledger & Recoverable Expense Engine

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-21

Adds one new table: owner_ledger_entries. Does NOT modify owners,
properties, or transactions — OwnerLedgerEntry references them
read-only (see app/models/owner_ledger.py for the full design note).

Note: the two new TransactionType enum values (RECOVERABLE_EXPENSE,
OWNER_REIMBURSEMENT) added to app/models/financial.py are plain Python
string constants, not a DB-level enum/check-constraint column — the
`transactions.transaction_type` column is already a free String(30)
(see 0001_initial_foundation.py / 0008_financial_management.py), so no
schema migration is needed for that change.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0021"
down_revision: Union[str, None] = "0020"
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
        "owner_ledger_entries",
        *_audit_columns(),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("expense_category", sa.String(50), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("entry_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("reversal_of_id", sa.Integer(), sa.ForeignKey("owner_ledger_entries.id"), nullable=True),
        sa.Column("reversed_by_id", sa.Integer(), sa.ForeignKey("owner_ledger_entries.id"), nullable=True),
    )
    op.create_index("ix_owner_ledger_entries_uuid", "owner_ledger_entries", ["uuid"])
    op.create_index("ix_owner_ledger_entries_owner_id", "owner_ledger_entries", ["owner_id"])
    op.create_index("ix_owner_ledger_entries_property_id", "owner_ledger_entries", ["property_id"])
    op.create_index("ix_owner_ledger_entries_transaction_date", "owner_ledger_entries", ["transaction_date"])
    op.create_index("ix_owner_ledger_entries_transaction_type", "owner_ledger_entries", ["transaction_type"])
    op.create_index("ix_owner_ledger_entries_entry_status", "owner_ledger_entries", ["entry_status"])


def downgrade() -> None:
    op.drop_table("owner_ledger_entries")
