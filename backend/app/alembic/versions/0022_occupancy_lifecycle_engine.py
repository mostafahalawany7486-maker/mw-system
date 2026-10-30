"""Phase 18: Occupancy & Unit Lifecycle Engine

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-21

Adds:
  - rental_contracts.move_out_notice_date (nullable) — the one new fact
    this phase needed that didn't already exist anywhere: distinguishing
    "tenant has formally given notice they're leaving" (Notice Period)
    from "contract is simply approaching its end_date" (Vacating Soon),
    which are listed as two distinct statuses in the spec but had no
    distinct underlying data before this.
  - unit_occupancy_overrides — administrative overrides for the six
    statuses that have no other natural event source anywhere in this
    codebase (Reserved, Cleaning, Inspection, Blocked, Renovation,
    Inactive) — see docs/occupancy-engine.md for why a lightweight
    override table was the right call here instead of either (a)
    building out full Reservation/Cleaning/Renovation subsystems no one
    asked for, or (b) silently ignoring six of the eleven required
    statuses.
  - occupancy_status_history — the audit trail. See
    app/business_workflows/occupancy/occupancy_engine.py's module
    docstring for why this is populated by comparing freshly-computed
    status against the last logged snapshot (via /occupancy/recalculate)
    rather than being written to directly — the engine's status is
    always LIVE-COMPUTED, never stored, so there is no "the status
    changed" write event to hook by default; recalculate is what turns
    a live computation into a discrete, auditable, timestamped event.

Does not touch properties.availability_status — it is left in place,
untouched, for backward compatibility with any existing code that reads
it (e.g. property_service.py's older building-summary aggregation).
The new engine never reads or writes it; see docs/occupancy-engine.md's
"Conflicts found" section for the full reasoning.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0022"
down_revision: Union[str, None] = "0021"
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
    op.add_column("rental_contracts", sa.Column("move_out_notice_date", sa.Date(), nullable=True))

    op.create_table(
        "unit_occupancy_overrides",
        *_audit_columns(),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("override_status", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("set_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("clear_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_unit_occupancy_overrides_uuid", "unit_occupancy_overrides", ["uuid"])
    op.create_index("ix_unit_occupancy_overrides_property_id", "unit_occupancy_overrides", ["property_id"])
    op.create_index("ix_unit_occupancy_overrides_override_status", "unit_occupancy_overrides", ["override_status"])
    # The query that matters most (get the active override for a unit) is
    # "property_id = X AND cleared_at IS NULL" — a composite index makes
    # that a direct index lookup instead of a property_id scan + filter.
    op.create_index("ix_unit_occupancy_overrides_active_lookup", "unit_occupancy_overrides", ["property_id", "cleared_at"])

    op.create_table(
        "occupancy_status_history",
        *_audit_columns(),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("previous_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(30), nullable=False, server_default="recalculate"),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_occupancy_status_history_uuid", "occupancy_status_history", ["uuid"])
    op.create_index("ix_occupancy_status_history_property_id", "occupancy_status_history", ["property_id"])
    op.create_index("ix_occupancy_status_history_changed_at", "occupancy_status_history", ["changed_at"])


def downgrade() -> None:
    op.drop_table("occupancy_status_history")
    op.drop_table("unit_occupancy_overrides")
    op.drop_column("rental_contracts", "move_out_notice_date")
