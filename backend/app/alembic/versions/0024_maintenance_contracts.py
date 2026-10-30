"""Maintenance Contracts extension — recurring/annual service contracts

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-22

Adds `maintenance_contracts` (new table — a recurring service contract
with a Contractor, covering a Property for a fixed term: elevator
maintenance, HVAC/AC servicing, generator servicing, fire-safety
inspection, etc.) plus one additive nullable column,
`maintenance_requests.maintenance_contract_id`, so an individual work
order can optionally be linked back to the contract it was performed
under.

Fully additive: no existing table is altered except for that one new
nullable FK column, and no existing row's data changes. Downgrade
reverses both steps cleanly.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0024"
down_revision: Union[str, None] = "0023"
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
        "maintenance_contracts",
        *_audit_columns(),
        sa.Column("contract_number", sa.String(20), nullable=False, unique=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractors.id"), nullable=False),
        sa.Column("service_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("signed_date", sa.Date(), nullable=True),
        sa.Column("visit_frequency", sa.String(20), nullable=False, server_default="quarterly"),
        sa.Column("visits_per_year", sa.Integer(), nullable=True),
        sa.Column("next_service_due_date", sa.Date(), nullable=True),
        sa.Column("annual_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=True),
        sa.Column("is_renewable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("renewal_notice_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("renewal_reminder_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("renewed_from_contract_id", sa.Integer(), sa.ForeignKey("maintenance_contracts.id"), nullable=True),
        sa.Column("contract_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("terminated_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_maintenance_contracts_uuid", "maintenance_contracts", ["uuid"])
    op.create_index("ix_maintenance_contracts_contract_number", "maintenance_contracts", ["contract_number"])
    op.create_index("ix_maintenance_contracts_property_id", "maintenance_contracts", ["property_id"])
    op.create_index("ix_maintenance_contracts_contractor_id", "maintenance_contracts", ["contractor_id"])
    op.create_index("ix_maintenance_contracts_service_type", "maintenance_contracts", ["service_type"])
    op.create_index("ix_maintenance_contracts_contract_status", "maintenance_contracts", ["contract_status"])
    # The query that matters most for renewal reminders: "active contracts
    # for this property", so a composite index makes that a direct lookup —
    # same pattern used for deposit_ledger_entries in migration 0023.
    op.create_index("ix_maintenance_contracts_property_status", "maintenance_contracts", ["property_id", "contract_status"])

    # Additive nullable FK on the existing Phase 9 table — every existing
    # maintenance_requests row gets NULL here and is otherwise untouched.
    op.add_column(
        "maintenance_requests",
        sa.Column("maintenance_contract_id", sa.Integer(), sa.ForeignKey("maintenance_contracts.id"), nullable=True),
    )
    op.create_index("ix_maintenance_requests_maintenance_contract_id", "maintenance_requests", ["maintenance_contract_id"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_requests_maintenance_contract_id", table_name="maintenance_requests")
    op.drop_column("maintenance_requests", "maintenance_contract_id")

    op.drop_index("ix_maintenance_contracts_property_status", table_name="maintenance_contracts")
    op.drop_index("ix_maintenance_contracts_contract_status", table_name="maintenance_contracts")
    op.drop_index("ix_maintenance_contracts_service_type", table_name="maintenance_contracts")
    op.drop_index("ix_maintenance_contracts_contractor_id", table_name="maintenance_contracts")
    op.drop_index("ix_maintenance_contracts_property_id", table_name="maintenance_contracts")
    op.drop_index("ix_maintenance_contracts_contract_number", table_name="maintenance_contracts")
    op.drop_index("ix_maintenance_contracts_uuid", table_name="maintenance_contracts")
    op.drop_table("maintenance_contracts")
