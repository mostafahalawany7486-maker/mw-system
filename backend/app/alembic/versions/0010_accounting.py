"""Phase 10: Accounting (Chart of Accounts, Journal Entries, GL, VAT)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
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
    # ---------------- Chart of Accounts ----------------
    op.create_table(
        "chart_of_accounts",
        *_audit_columns(),
        sa.Column("account_code", sa.String(20), nullable=False, unique=True),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("account_subtype", sa.String(50), nullable=True),
        sa.Column("parent_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=True),
        sa.Column("allow_posting", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_chart_of_accounts_uuid", "chart_of_accounts", ["uuid"])
    op.create_index("ix_chart_of_accounts_account_code", "chart_of_accounts", ["account_code"])
    op.create_index("ix_chart_of_accounts_account_type", "chart_of_accounts", ["account_type"])
    op.create_index("ix_chart_of_accounts_parent_account_id", "chart_of_accounts", ["parent_account_id"])

    # ---------------- Cost Centers ----------------
    op.create_table(
        "cost_centers",
        *_audit_columns(),
        sa.Column("cost_center_code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_cost_centers_uuid", "cost_centers", ["uuid"])
    op.create_index("ix_cost_centers_cost_center_code", "cost_centers", ["cost_center_code"])

    # ---------------- VAT Rates ----------------
    op.create_table(
        "vat_rates",
        *_audit_columns(),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("rate_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("gl_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_vat_rates_uuid", "vat_rates", ["uuid"])
    op.create_index("ix_vat_rates_code", "vat_rates", ["code"])

    # ---------------- Posting Rules ----------------
    op.create_table(
        "posting_rules",
        *_audit_columns(),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("offset_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("vat_rate_id", sa.Integer(), sa.ForeignKey("vat_rates.id"), nullable=True),
        sa.Column("cost_center_id", sa.Integer(), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_posting_rules_uuid", "posting_rules", ["uuid"])
    op.create_index("ix_posting_rules_transaction_type", "posting_rules", ["transaction_type"])
    op.create_index("ix_posting_rules_category", "posting_rules", ["category"])

    # ---------------- Journal Entries ----------------
    op.create_table(
        "journal_entries",
        *_audit_columns(),
        sa.Column("entry_number", sa.String(20), nullable=False, unique=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("source_type", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("source_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("entry_status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),
    )
    op.create_index("ix_journal_entries_uuid", "journal_entries", ["uuid"])
    op.create_index("ix_journal_entries_entry_number", "journal_entries", ["entry_number"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_source_type", "journal_entries", ["source_type"])
    op.create_index("ix_journal_entries_source_transaction_id", "journal_entries", ["source_transaction_id"])
    op.create_index("ix_journal_entries_entry_status", "journal_entries", ["entry_status"])

    # ---------------- Journal Entry Lines ----------------
    op.create_table(
        "journal_entry_lines",
        *_audit_columns(),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("cost_center_id", sa.Integer(), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("debit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("vat_rate_id", sa.Integer(), sa.ForeignKey("vat_rates.id"), nullable=True),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_journal_entry_lines_uuid", "journal_entry_lines", ["uuid"])
    op.create_index("ix_journal_entry_lines_journal_entry_id", "journal_entry_lines", ["journal_entry_id"])
    op.create_index("ix_journal_entry_lines_account_id", "journal_entry_lines", ["account_id"])
    op.create_index("ix_journal_entry_lines_cost_center_id", "journal_entry_lines", ["cost_center_id"])

    # ---------------- Additive link: FinancialAccount -> ChartOfAccount ----------------
    op.add_column("financial_accounts", sa.Column("gl_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("financial_accounts", "gl_account_id")
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
    op.drop_table("posting_rules")
    op.drop_table("vat_rates")
    op.drop_table("cost_centers")
    op.drop_table("chart_of_accounts")
