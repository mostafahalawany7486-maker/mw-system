"""Phase 1: Foundation - auth, RBAC, organization, system infra tables

Revision ID: 0001
Revises:
Create Date: 2026-07-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def _audit_columns():
    """The mandatory columns every table must have, per project DB standards."""
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # ---------------- Roles & Permissions (created before users, but FK to
    # users for created_by/updated_by is added later via ALTER, since users
    # doesn't exist yet - see use_alter pattern below) ----------------
    op.create_table(
        "roles",
        *_audit_columns(),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_roles_uuid", "roles", ["uuid"])

    op.create_table(
        "permissions",
        *_audit_columns(),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])
    op.create_index("ix_permissions_module", "permissions", ["module"])
    op.create_index("ix_permissions_uuid", "permissions", ["uuid"])

    # ---------------- Countries / Cities / Currencies (no user FK needed
    # at row level besides audit) ----------------
    op.create_table(
        "countries",
        *_audit_columns(),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("iso_code2", sa.String(2), nullable=False, unique=True),
        sa.Column("iso_code3", sa.String(3), nullable=False, unique=True),
        sa.Column("phone_code", sa.String(10), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_countries_uuid", "countries", ["uuid"])

    op.create_table(
        "cities",
        *_audit_columns(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_cities_uuid", "cities", ["uuid"])

    op.create_table(
        "currencies",
        *_audit_columns(),
        sa.Column("code", sa.String(3), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("exchange_rate_to_base", sa.Numeric(18, 6), nullable=False, server_default="1"),
        sa.Column("is_base_currency", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_currencies_uuid", "currencies", ["uuid"])

    # ---------------- Branches (before users, since users.branch_id refs it;
    # branches.manager_id refs users -> added via ALTER after users exists) ----------------
    op.create_table(
        "branches",
        *_audit_columns(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("is_head_office", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_branches_uuid", "branches", ["uuid"])

    # ---------------- Users ----------------
    op.create_table(
        "users",
        *_audit_columns(),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_uuid", "users", ["uuid"])

    # Now that users exists, wire up the deferred FKs (use_alter columns)
    op.create_foreign_key("fk_roles_created_by_users", "roles", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_roles_updated_by_users", "roles", "users", ["updated_by"], ["id"])
    op.create_foreign_key("fk_permissions_created_by_users", "permissions", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_permissions_updated_by_users", "permissions", "users", ["updated_by"], ["id"])
    op.create_foreign_key("fk_countries_created_by_users", "countries", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_countries_updated_by_users", "countries", "users", ["updated_by"], ["id"])
    op.create_foreign_key("fk_cities_created_by_users", "cities", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_cities_updated_by_users", "cities", "users", ["updated_by"], ["id"])
    op.create_foreign_key("fk_currencies_created_by_users", "currencies", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_currencies_updated_by_users", "currencies", "users", ["updated_by"], ["id"])
    op.create_foreign_key("fk_branches_created_by_users", "branches", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_branches_updated_by_users", "branches", "users", ["updated_by"], ["id"])
    op.create_foreign_key("fk_branches_manager_users", "branches", "users", ["manager_id"], ["id"])
    op.create_foreign_key("fk_users_created_by_users", "users", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_users_updated_by_users", "users", "users", ["updated_by"], ["id"])

    # ---------------- Role <-> Permission association ----------------
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    # ---------------- Company Profile ----------------
    op.create_table(
        "company_profile",
        *_audit_columns(),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255), nullable=True),
        sa.Column("registration_number", sa.String(100), nullable=True),
        sa.Column("tax_number", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=True),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=True),
        sa.Column("base_currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("default_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_company_profile_uuid", "company_profile", ["uuid"])

    # ---------------- System Settings ----------------
    op.create_table(
        "system_settings",
        *_audit_columns(),
        sa.Column("key", sa.String(150), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_editable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])
    op.create_index("ix_system_settings_uuid", "system_settings", ["uuid"])

    # ---------------- Attachments ----------------
    op.create_table(
        "attachments",
        *_audit_columns(),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_url", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("storage_backend", sa.String(20), nullable=False, server_default="local"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_attachments_entity", "attachments", ["entity_type", "entity_id"])
    op.create_index("ix_attachments_uuid", "attachments", ["uuid"])

    # ---------------- Notes ----------------
    op.create_table(
        "notes",
        *_audit_columns(),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_notes_entity", "notes", ["entity_type", "entity_id"])
    op.create_index("ix_notes_uuid", "notes", ["uuid"])

    # ---------------- Activity Log ----------------
    op.create_table(
        "activity_logs",
        *_audit_columns(),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_activity_logs_entity", "activity_logs", ["entity_type", "entity_id"])
    op.create_index("ix_activity_logs_uuid", "activity_logs", ["uuid"])

    # ---------------- Audit Log ----------------
    op.create_table(
        "audit_logs",
        *_audit_columns(),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_uuid", "audit_logs", ["uuid"])

    # ---------------- Notifications ----------------
    op.create_table(
        "notifications",
        *_audit_columns(),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False, server_default="info"),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="in_app"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_notifications_recipient", "notifications", ["recipient_id"])
    op.create_index("ix_notifications_uuid", "notifications", ["uuid"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("activity_logs")
    op.drop_table("notes")
    op.drop_table("attachments")
    op.drop_table("system_settings")
    op.drop_table("company_profile")
    op.drop_table("role_permissions")
    op.drop_constraint("fk_users_updated_by_users", "users", type_="foreignkey")
    op.drop_constraint("fk_users_created_by_users", "users", type_="foreignkey")
    op.drop_constraint("fk_branches_manager_users", "branches", type_="foreignkey")
    op.drop_constraint("fk_branches_updated_by_users", "branches", type_="foreignkey")
    op.drop_constraint("fk_branches_created_by_users", "branches", type_="foreignkey")
    op.drop_constraint("fk_currencies_updated_by_users", "currencies", type_="foreignkey")
    op.drop_constraint("fk_currencies_created_by_users", "currencies", type_="foreignkey")
    op.drop_constraint("fk_cities_updated_by_users", "cities", type_="foreignkey")
    op.drop_constraint("fk_cities_created_by_users", "cities", type_="foreignkey")
    op.drop_constraint("fk_countries_updated_by_users", "countries", type_="foreignkey")
    op.drop_constraint("fk_countries_created_by_users", "countries", type_="foreignkey")
    op.drop_constraint("fk_permissions_updated_by_users", "permissions", type_="foreignkey")
    op.drop_constraint("fk_permissions_created_by_users", "permissions", type_="foreignkey")
    op.drop_constraint("fk_roles_updated_by_users", "roles", type_="foreignkey")
    op.drop_constraint("fk_roles_created_by_users", "roles", type_="foreignkey")
    op.drop_table("users")
    op.drop_table("branches")
    op.drop_table("currencies")
    op.drop_table("cities")
    op.drop_table("countries")
    op.drop_table("permissions")
    op.drop_table("roles")
