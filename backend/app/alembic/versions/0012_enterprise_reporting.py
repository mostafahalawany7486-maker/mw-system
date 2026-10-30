"""Enterprise Reporting: report_schedules table (Export Scheduling)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-18

Purely additive — one new table, no existing tables touched.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("export_format", sa.String(10), nullable=False, server_default="pdf"),
        sa.Column("frequency", sa.String(10), nullable=False, server_default="monthly"),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_export_attachment_id", sa.Integer(), sa.ForeignKey("attachments.id"), nullable=True),
    )
    op.create_index("ix_report_schedules_uuid", "report_schedules", ["uuid"])
    op.create_index("ix_report_schedules_report_type", "report_schedules", ["report_type"])


def downgrade() -> None:
    op.drop_table("report_schedules")
