"""Phase 6: Tenant Management

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-17

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
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
    # ---------------- Tenants ----------------
    op.create_table(
        "tenants",
        *_audit_columns(),
        sa.Column("tenant_code", sa.String(20), nullable=False, unique=True),
        sa.Column("tenant_type", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("national_id", sa.String(50), nullable=True),
        sa.Column("passport_number", sa.String(50), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("nationality_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("commercial_registration_number", sa.String(100), nullable=True),
        sa.Column("tax_number", sa.String(100), nullable=True),
        sa.Column("contact_person_name", sa.String(150), nullable=True),
        sa.Column("contact_person_title", sa.String(100), nullable=True),
        sa.Column("primary_email", sa.String(255), nullable=True),
        sa.Column("primary_phone", sa.String(30), nullable=True),
        sa.Column("secondary_phone", sa.String(30), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("notes_summary", sa.Text(), nullable=True),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("blacklist_reason", sa.Text(), nullable=True),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blacklisted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_tenants_uuid", "tenants", ["uuid"])
    op.create_index("ix_tenants_tenant_code", "tenants", ["tenant_code"])
    op.create_index("ix_tenants_tenant_type", "tenants", ["tenant_type"])
    op.create_index("ix_tenants_national_id", "tenants", ["national_id"])
    op.create_index("ix_tenants_passport_number", "tenants", ["passport_number"])
    op.create_index("ix_tenants_commercial_registration_number", "tenants", ["commercial_registration_number"])
    op.create_index("ix_tenants_primary_email", "tenants", ["primary_email"])
    op.create_index("ix_tenants_is_blacklisted", "tenants", ["is_blacklisted"])

    # ---------------- Tenant Contacts ----------------
    op.create_table(
        "tenant_contacts",
        *_audit_columns(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("designation", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_tenant_contacts_tenant_id", "tenant_contacts", ["tenant_id"])
    op.create_index("ix_tenant_contacts_uuid", "tenant_contacts", ["uuid"])

    # ---------------- Tenant Emergency Contacts ----------------
    op.create_table(
        "tenant_emergency_contacts",
        *_audit_columns(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=True),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_tenant_emergency_contacts_tenant_id", "tenant_emergency_contacts", ["tenant_id"])
    op.create_index("ix_tenant_emergency_contacts_uuid", "tenant_emergency_contacts", ["uuid"])

    # ---------------- Tenant Documents ----------------
    op.create_table(
        "tenant_documents",
        *_audit_columns(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column("description", sa.String(500), nullable=True),
    )
    op.create_index("ix_tenant_documents_tenant_id", "tenant_documents", ["tenant_id"])
    op.create_index("ix_tenant_documents_uuid", "tenant_documents", ["uuid"])

    # ---------------- Tenant Ratings ----------------
    op.create_table(
        "tenant_ratings",
        *_audit_columns(),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating_value", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_tenant_ratings_tenant_id", "tenant_ratings", ["tenant_id"])
    op.create_index("ix_tenant_ratings_uuid", "tenant_ratings", ["uuid"])


def downgrade() -> None:
    op.drop_table("tenant_ratings")
    op.drop_table("tenant_documents")
    op.drop_table("tenant_emergency_contacts")
    op.drop_table("tenant_contacts")
    op.drop_table("tenants")
