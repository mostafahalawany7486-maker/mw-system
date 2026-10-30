"""Phase 9: Maintenance

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
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
    # ---------------- Contractors ----------------
    op.create_table(
        "contractors",
        *_audit_columns(),
        sa.Column("contractor_code", sa.String(20), nullable=False, unique=True),
        sa.Column("company_name", sa.String(150), nullable=False),
        sa.Column("contact_person", sa.String(150), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("specialty", sa.String(50), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_contractors_uuid", "contractors", ["uuid"])
    op.create_index("ix_contractors_contractor_code", "contractors", ["contractor_code"])
    op.create_index("ix_contractors_specialty", "contractors", ["specialty"])

    # ---------------- Technicians ----------------
    op.create_table(
        "technicians",
        *_audit_columns(),
        sa.Column("technician_code", sa.String(20), nullable=False, unique=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("specialty", sa.String(50), nullable=True),
        sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractors.id"), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_technicians_uuid", "technicians", ["uuid"])
    op.create_index("ix_technicians_technician_code", "technicians", ["technician_code"])
    op.create_index("ix_technicians_specialty", "technicians", ["specialty"])
    op.create_index("ix_technicians_contractor_id", "technicians", ["contractor_id"])

    # ---------------- Maintenance Requests ----------------
    op.create_table(
        "maintenance_requests",
        *_audit_columns(),
        sa.Column("request_number", sa.String(20), nullable=False, unique=True),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("rental_contract_id", sa.Integer(), sa.ForeignKey("rental_contracts.id"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("maintenance_status", sa.String(20), nullable=False, server_default="reported"),
        sa.Column("reported_date", sa.Date(), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("assigned_contractor_id", sa.Integer(), sa.ForeignKey("contractors.id"), nullable=True),
        sa.Column("assigned_technician_id", sa.Integer(), sa.ForeignKey("technicians.id"), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("on_hold_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_maintenance_requests_uuid", "maintenance_requests", ["uuid"])
    op.create_index("ix_maintenance_requests_request_number", "maintenance_requests", ["request_number"])
    op.create_index("ix_maintenance_requests_property_id", "maintenance_requests", ["property_id"])
    op.create_index("ix_maintenance_requests_tenant_id", "maintenance_requests", ["tenant_id"])
    op.create_index("ix_maintenance_requests_category", "maintenance_requests", ["category"])
    op.create_index("ix_maintenance_requests_priority", "maintenance_requests", ["priority"])
    op.create_index("ix_maintenance_requests_maintenance_status", "maintenance_requests", ["maintenance_status"])

    # ---------------- Materials ----------------
    op.create_table(
        "maintenance_materials",
        *_audit_columns(),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("supplier", sa.String(150), nullable=True),
    )
    op.create_index("ix_maintenance_materials_uuid", "maintenance_materials", ["uuid"])
    op.create_index("ix_maintenance_materials_request_id", "maintenance_materials", ["request_id"])

    # ---------------- Labor Costs ----------------
    op.create_table(
        "maintenance_labor_costs",
        *_audit_columns(),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("technician_id", sa.Integer(), sa.ForeignKey("technicians.id"), nullable=True),
        sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractors.id"), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=True),
    )
    op.create_index("ix_maintenance_labor_costs_uuid", "maintenance_labor_costs", ["uuid"])
    op.create_index("ix_maintenance_labor_costs_request_id", "maintenance_labor_costs", ["request_id"])

    # ---------------- Photos ----------------
    op.create_table(
        "maintenance_photos",
        *_audit_columns(),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("maintenance_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_type", sa.String(10), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column("caption", sa.String(255), nullable=True),
    )
    op.create_index("ix_maintenance_photos_uuid", "maintenance_photos", ["uuid"])
    op.create_index("ix_maintenance_photos_request_id", "maintenance_photos", ["request_id"])
    op.create_index("ix_maintenance_photos_photo_type", "maintenance_photos", ["photo_type"])


def downgrade() -> None:
    op.drop_table("maintenance_photos")
    op.drop_table("maintenance_labor_costs")
    op.drop_table("maintenance_materials")
    op.drop_table("maintenance_requests")
    op.drop_table("technicians")
    op.drop_table("contractors")
