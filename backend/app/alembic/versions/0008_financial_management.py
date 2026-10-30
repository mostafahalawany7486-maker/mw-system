"""Phase 8: Financial Management

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
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
    # ---------------- Financial Accounts (Cash & Bank) ----------------
    op.create_table(
        "financial_accounts",
        *_audit_columns(),
        sa.Column("account_code", sa.String(20), nullable=False, unique=True),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("bank_name", sa.String(150), nullable=True),
        sa.Column("account_number", sa.String(100), nullable=True),
        sa.Column("iban", sa.String(50), nullable=True),
        sa.Column("currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_financial_accounts_uuid", "financial_accounts", ["uuid"])
    op.create_index("ix_financial_accounts_account_code", "financial_accounts", ["account_code"])
    op.create_index("ix_financial_accounts_account_type", "financial_accounts", ["account_type"])

    # ---------------- Transactions (unified ledger) ----------------
    op.create_table(
        "transactions",
        *_audit_columns(),
        sa.Column("transaction_number", sa.String(20), nullable=False, unique=True),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("transaction_status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("financial_accounts.id"), nullable=False),
        sa.Column("transfer_pair_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id"), nullable=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True),
        sa.Column("rental_contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id"), nullable=True),
        sa.Column("rental_installment_id", sa.Integer(), sa.ForeignKey("rental_payment_installments.id"), nullable=True),
        sa.Column("lease_agreement_id", sa.Integer(), sa.ForeignKey("lease_agreements.id"), nullable=True),
        sa.Column("lease_installment_id", sa.Integer(), sa.ForeignKey("lease_payment_installments.id"), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("payment_method", sa.String(30), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_transactions_uuid", "transactions", ["uuid"])
    op.create_index("ix_transactions_transaction_number", "transactions", ["transaction_number"])
    op.create_index("ix_transactions_transaction_type", "transactions", ["transaction_type"])
    op.create_index("ix_transactions_transaction_status", "transactions", ["transaction_status"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_tenant_id", "transactions", ["tenant_id"])
    op.create_index("ix_transactions_owner_id", "transactions", ["owner_id"])

    # ---------------- Receipts ----------------
    op.create_table(
        "receipts",
        *_audit_columns(),
        sa.Column("receipt_number", sa.String(20), nullable=False, unique=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("issued_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_receipts_uuid", "receipts", ["uuid"])
    op.create_index("ix_receipts_receipt_number", "receipts", ["receipt_number"])

    # ---------------- Invoices ----------------
    op.create_table(
        "invoices",
        *_audit_columns(),
        sa.Column("invoice_number", sa.String(20), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("rental_contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("invoice_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("paid_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
    )
    op.create_index("ix_invoices_uuid", "invoices", ["uuid"])
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_invoice_status", "invoices", ["invoice_status"])


def downgrade() -> None:
    op.drop_table("invoices")
    op.drop_table("receipts")
    op.drop_table("transactions")
    op.drop_table("financial_accounts")
