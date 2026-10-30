"""Phase 2: Property Owners module

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
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
    # ---------------- Owners ----------------
    op.create_table(
        "owners",
        *_audit_columns(),
        sa.Column("owner_code", sa.String(20), nullable=False, unique=True),
        sa.Column("owner_type", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("national_id", sa.String(50), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("nationality_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("registration_number", sa.String(100), nullable=True),
        sa.Column("tax_number", sa.String(100), nullable=True),
        sa.Column("contact_person_name", sa.String(150), nullable=True),
        sa.Column("contact_person_title", sa.String(100), nullable=True),
        sa.Column("primary_email", sa.String(255), nullable=True),
        sa.Column("primary_phone", sa.String(30), nullable=True),
        sa.Column("secondary_phone", sa.String(30), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("notes_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_owners_uuid", "owners", ["uuid"])
    op.create_index("ix_owners_owner_code", "owners", ["owner_code"])
    op.create_index("ix_owners_owner_type", "owners", ["owner_type"])
    op.create_index("ix_owners_national_id", "owners", ["national_id"])
    op.create_index("ix_owners_primary_email", "owners", ["primary_email"])

    # ---------------- Owner Addresses ----------------
    op.create_table(
        "owner_addresses",
        *_audit_columns(),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("address_type", sa.String(30), nullable=False, server_default="mailing"),
        sa.Column("line1", sa.String(255), nullable=False),
        sa.Column("line2", sa.String(255), nullable=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_owner_addresses_owner_id", "owner_addresses", ["owner_id"])
    op.create_index("ix_owner_addresses_uuid", "owner_addresses", ["uuid"])

    # ---------------- Owner Bank Accounts ----------------
    op.create_table(
        "owner_bank_accounts",
        *_audit_columns(),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_name", sa.String(150), nullable=False),
        sa.Column("account_holder_name", sa.String(150), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=True),
        sa.Column("iban", sa.String(50), nullable=True),
        sa.Column("swift_code", sa.String(20), nullable=True),
        sa.Column("currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_owner_bank_accounts_owner_id", "owner_bank_accounts", ["owner_id"])
    op.create_index("ix_owner_bank_accounts_uuid", "owner_bank_accounts", ["uuid"])

    # ---------------- Owner Contacts ----------------
    op.create_table(
        "owner_contacts",
        *_audit_columns(),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("designation", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_owner_contacts_owner_id", "owner_contacts", ["owner_id"])
    op.create_index("ix_owner_contacts_uuid", "owner_contacts", ["uuid"])

    # ---------------- Owner Documents ----------------
    op.create_table(
        "owner_documents",
        *_audit_columns(),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("owners.id", ondelete="CASCADE"), nullable=False),
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
    op.create_index("ix_owner_documents_owner_id", "owner_documents", ["owner_id"])
    op.create_index("ix_owner_documents_uuid", "owner_documents", ["uuid"])


def downgrade() -> None:
    op.drop_table("owner_documents")
    op.drop_table("owner_contacts")
    op.drop_table("owner_bank_accounts")
    op.drop_table("owner_addresses")
    op.drop_table("owners")
