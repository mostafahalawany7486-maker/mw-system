"""Phase 4: Property Management

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
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
    # ---------------- Amenities (lookup) ----------------
    op.create_table(
        "amenities",
        *_audit_columns(),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=True),
    )
    op.create_index("ix_amenities_uuid", "amenities", ["uuid"])

    # ---------------- Properties ----------------
    op.create_table(
        "properties",
        *_audit_columns(),
        sa.Column("property_code", sa.String(20), nullable=False, unique=True),
        sa.Column("internal_code", sa.String(50), nullable=True),
        sa.Column("property_type", sa.String(30), nullable=False),
        sa.Column("parent_property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("area_sqm", sa.Numeric(10, 2), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("floor_number", sa.String(20), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("furnishing_status", sa.String(20), nullable=True),
        sa.Column("availability_status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("notes_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_properties_uuid", "properties", ["uuid"])
    op.create_index("ix_properties_property_code", "properties", ["property_code"])
    op.create_index("ix_properties_internal_code", "properties", ["internal_code"])
    op.create_index("ix_properties_property_type", "properties", ["property_type"])
    op.create_index("ix_properties_owner_id", "properties", ["owner_id"])
    op.create_index("ix_properties_availability_status", "properties", ["availability_status"])

    # ---------------- Property <-> Amenity association ----------------
    op.create_table(
        "property_amenities",
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("amenity_id", sa.Integer(), sa.ForeignKey("amenities.id", ondelete="CASCADE"), primary_key=True),
    )

    # ---------------- Property Images ----------------
    op.create_table(
        "property_images",
        *_audit_columns(),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column("caption", sa.String(255), nullable=True),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_property_images_property_id", "property_images", ["property_id"])
    op.create_index("ix_property_images_uuid", "property_images", ["uuid"])

    # ---------------- Property Documents ----------------
    op.create_table(
        "property_documents",
        *_audit_columns(),
        sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
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
    op.create_index("ix_property_documents_property_id", "property_documents", ["property_id"])
    op.create_index("ix_property_documents_uuid", "property_documents", ["uuid"])

    # ---------------- Link Lease Agreements to formal Properties (additive) ----------------
    op.add_column("lease_agreements", sa.Column("property_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True))
    op.create_index("ix_lease_agreements_property_id", "lease_agreements", ["property_id"])


def downgrade() -> None:
    op.drop_index("ix_lease_agreements_property_id", table_name="lease_agreements")
    op.drop_column("lease_agreements", "property_id")
    op.drop_table("property_documents")
    op.drop_table("property_images")
    op.drop_table("property_amenities")
    op.drop_table("properties")
    op.drop_table("amenities")
