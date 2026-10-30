"""Property Profit Center: add property_id to invoices and journal_entry_lines

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-18

Purely additive — two nullable FK columns. No existing data is touched;
every existing invoice/journal_entry_line simply has property_id = NULL
until re-saved or backfilled, and all existing queries/behavior are
unaffected.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True))
    op.create_index("ix_invoices_property_id", "invoices", ["property_id"])

    op.add_column("journal_entry_lines", sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True))
    op.create_index("ix_journal_entry_lines_property_id", "journal_entry_lines", ["property_id"])

    # transactions.property_id already existed (Phase 8) but was never
    # indexed; the new profit-center reports filter on it heavily.
    op.create_index("ix_transactions_property_id", "transactions", ["property_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_property_id", table_name="transactions")

    op.drop_index("ix_journal_entry_lines_property_id", table_name="journal_entry_lines")
    op.drop_column("journal_entry_lines", "property_id")

    op.drop_index("ix_invoices_property_id", table_name="invoices")
    op.drop_column("invoices", "property_id")
