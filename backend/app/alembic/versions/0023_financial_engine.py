"""Phase 19: Financial Engine — Security Deposit lifecycle ledger

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-21

The one new table this phase needed — see app/models/financial_engine.py's
module docstring for why every other "ledger" the spec asks for is a
live view over existing tables (Transaction, FinancialAccount,
OwnerLedgerEntry) rather than a new table, and why the Security Deposit
lifecycle specifically could not be.

Does not touch rental_contracts.security_deposit_amount/status or
lease_agreements.security_deposit_amount/status (Phase 3/7) — those
columns remain the "current snapshot" (amount still held, current
status); DepositLedgerEntry is the full history behind that snapshot,
updated in lockstep by deposit_service.py rather than replacing those
columns.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0023"
down_revision: Union[str, None] = "0022"
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
        "deposit_ledger_entries",
        *_audit_columns(),
        sa.Column("contract_type", sa.String(10), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("action_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_deposit_ledger_entries_uuid", "deposit_ledger_entries", ["uuid"])
    op.create_index("ix_deposit_ledger_entries_contract_type", "deposit_ledger_entries", ["contract_type"])
    op.create_index("ix_deposit_ledger_entries_contract_id", "deposit_ledger_entries", ["contract_id"])
    op.create_index("ix_deposit_ledger_entries_action", "deposit_ledger_entries", ["action"])
    # The query that matters most: "every entry for this one contract's
    # deposit, in order" — a composite index makes that a direct lookup.
    op.create_index("ix_deposit_ledger_entries_contract_lookup", "deposit_ledger_entries", ["contract_type", "contract_id"])


def downgrade() -> None:
    op.drop_table("deposit_ledger_entries")
