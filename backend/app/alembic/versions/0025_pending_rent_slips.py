"""Pending Rent Slips — pre-collection printable slips

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-23

New table only — `pending_rent_slips`. Does not touch `rent_vouchers`,
`transactions`, or any other existing table/column. See
app/models/pending_rent_slip.py for the full design rationale.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_rent_slips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("slip_number", sa.String(20), nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("copy_type", sa.String(10), nullable=False),
        sa.Column("rental_month", sa.Date(), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("barcode_value", sa.String(100), nullable=False, unique=True),
        sa.Column("print_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Note: `status` above (inherited audit column, active/archived)
        # is unrelated to the slip's own pending/collected/cancelled
        # workflow state — that lives in a separate column below to
        # avoid overloading the shared archive-status column with
        # business-workflow meaning (the same reasoning already applied
        # throughout this codebase's other extensions).
        sa.Column("slip_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index("ix_pending_rent_slips_uuid", "pending_rent_slips", ["uuid"])
    op.create_index("ix_pending_rent_slips_slip_number", "pending_rent_slips", ["slip_number"])
    op.create_index("ix_pending_rent_slips_tenant_id", "pending_rent_slips", ["tenant_id"])
    op.create_index("ix_pending_rent_slips_property_id", "pending_rent_slips", ["property_id"])
    op.create_index("ix_pending_rent_slips_copy_type", "pending_rent_slips", ["copy_type"])
    op.create_index("ix_pending_rent_slips_barcode_value", "pending_rent_slips", ["barcode_value"])
    op.create_index("ix_pending_rent_slips_slip_status", "pending_rent_slips", ["slip_status"])
    op.create_unique_constraint(
        "uq_pending_slip_tenant_property_month_copy", "pending_rent_slips",
        ["tenant_id", "property_id", "rental_month", "copy_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_pending_slip_tenant_property_month_copy", "pending_rent_slips", type_="unique")
    op.drop_index("ix_pending_rent_slips_slip_status", table_name="pending_rent_slips")
    op.drop_index("ix_pending_rent_slips_barcode_value", table_name="pending_rent_slips")
    op.drop_index("ix_pending_rent_slips_copy_type", table_name="pending_rent_slips")
    op.drop_index("ix_pending_rent_slips_property_id", table_name="pending_rent_slips")
    op.drop_index("ix_pending_rent_slips_tenant_id", table_name="pending_rent_slips")
    op.drop_index("ix_pending_rent_slips_slip_number", table_name="pending_rent_slips")
    op.drop_index("ix_pending_rent_slips_uuid", table_name="pending_rent_slips")
    op.drop_table("pending_rent_slips")
