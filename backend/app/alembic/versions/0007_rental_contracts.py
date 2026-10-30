"""Phase 7: Rental Contracts (Company -> Tenant)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
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
        "rental_contracts",
        *_audit_columns(),
        sa.Column("contract_number", sa.String(20), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("signed_date", sa.Date(), nullable=True),
        sa.Column("is_renewable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("renewal_notice_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("renewal_reminder_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("renewed_from_contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id"), nullable=True),
        sa.Column("payment_frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("rent_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=True),
        sa.Column("security_deposit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("security_deposit_status", sa.String(20), nullable=False, server_default="held"),
        sa.Column("discount_type", sa.String(20), nullable=False, server_default="none"),
        sa.Column("discount_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_reason", sa.String(255), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("late_fee_type", sa.String(20), nullable=False, server_default="fixed"),
        sa.Column("late_fee_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("late_fee_grace_period_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("contract_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("terminated_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("notes_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_rental_contracts_uuid", "rental_contracts", ["uuid"])
    op.create_index("ix_rental_contracts_contract_number", "rental_contracts", ["contract_number"])
    op.create_index("ix_rental_contracts_tenant_id", "rental_contracts", ["tenant_id"])
    op.create_index("ix_rental_contracts_property_id", "rental_contracts", ["property_id"])
    op.create_index("ix_rental_contracts_contract_status", "rental_contracts", ["contract_status"])

    op.create_table(
        "rental_payment_installments",
        *_audit_columns(),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("late_fee_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
    )
    op.create_index("ix_rental_payment_installments_contract_id", "rental_payment_installments", ["contract_id"])
    op.create_index("ix_rental_payment_installments_payment_status", "rental_payment_installments", ["payment_status"])
    op.create_index("ix_rental_payment_installments_uuid", "rental_payment_installments", ["uuid"])


def downgrade() -> None:
    op.drop_table("rental_payment_installments")
    op.drop_table("rental_contracts")
