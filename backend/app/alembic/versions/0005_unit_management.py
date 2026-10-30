"""Phase 5: Unit Management

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
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
    # ---------------- Floors ----------------
    op.create_table(
        "floors",
        *_audit_columns(),
        sa.Column("building_id", sa.Integer(), sa.ForeignKey("properties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("floor_number", sa.String(20), nullable=False),
        sa.Column("floor_name", sa.String(100), nullable=True),
        sa.Column("total_units", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_floors_uuid", "floors", ["uuid"])
    op.create_index("ix_floors_building_id", "floors", ["building_id"])

    # ---------------- Unit-management columns on properties (additive) ----------------
    op.add_column("properties", sa.Column("floor_id", sa.Integer(), sa.ForeignKey("floors.id"), nullable=True))
    op.add_column("properties", sa.Column("unit_number", sa.String(30), nullable=True))
    op.add_column("properties", sa.Column("rent_price", sa.Numeric(14, 2), nullable=True))
    op.add_column("properties", sa.Column("electricity_meter_number", sa.String(50), nullable=True))
    op.add_column("properties", sa.Column("water_meter_number", sa.String(50), nullable=True))
    op.add_column("properties", sa.Column("parking_space_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True))
    op.add_column("properties", sa.Column("storage_space_id", sa.Integer(), sa.ForeignKey("properties.id"), nullable=True))

    op.create_index("ix_properties_floor_id", "properties", ["floor_id"])
    op.create_index("ix_properties_unit_number", "properties", ["unit_number"])


def downgrade() -> None:
    op.drop_index("ix_properties_unit_number", table_name="properties")
    op.drop_index("ix_properties_floor_id", table_name="properties")
    op.drop_column("properties", "storage_space_id")
    op.drop_column("properties", "parking_space_id")
    op.drop_column("properties", "water_meter_number")
    op.drop_column("properties", "electricity_meter_number")
    op.drop_column("properties", "rent_price")
    op.drop_column("properties", "unit_number")
    op.drop_column("properties", "floor_id")
    op.drop_table("floors")
