"""Phase 2.0: Property Structure & Unit Management Enhancement

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-19

Purely additive — no new tables. The requested Owner -> Property ->
Floors -> Units -> Rental Contract -> Tenant hierarchy already exists
(Phase 4/5's `Property` self-reference via parent_property_id + `Floor`),
and the requested container types (Building, Villa, Commercial Building,
Commercial Complex, Warehouse, Land, Mixed Use) are all still the single
`properties` table with a `property_type` discriminator — three new
values (commercial_building, commercial_complex, mixed_use) added at the
application layer only (see app/models/property.py PropertyType), no DB
constraint change needed since property_type has always been a plain
VARCHAR validated in the Pydantic schema, not a DB enum/check constraint.

What IS new here: five nullable columns for physical characteristics the
existing schema had no field for at all (elevators, parking capacity,
garden, pool, maid room) — everything else the spec asks for (unit
counts, occupancy, vacant/reserved/maintenance counts, active/expired
contracts) is computed on read (see property_service.py /
property_repository.py), never stored, per the spec's own "must be
dynamic and never entered manually" requirement.

Also adds three indexes the Performance section of the spec calls for:
properties.parent_property_id, properties.branch_id, and
properties.city_id had no indexes despite all three being active filter
columns on GET /properties (parent_property_id is additionally the
column every building/villa -> units lookup filters on — list_units,
get_building_summary, get_property_summary, the new units report, and
the dashboard roll-ups all hit it).
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("elevators", sa.Integer(), nullable=True))
    op.add_column("properties", sa.Column("parking_spaces_count", sa.Integer(), nullable=True))
    op.add_column("properties", sa.Column("garden", sa.Boolean(), nullable=True))
    op.add_column("properties", sa.Column("swimming_pool", sa.Boolean(), nullable=True))
    op.add_column("properties", sa.Column("maid_room", sa.Boolean(), nullable=True))
    op.create_index("ix_properties_parent_property_id", "properties", ["parent_property_id"])
    op.create_index("ix_properties_branch_id", "properties", ["branch_id"])
    op.create_index("ix_properties_city_id", "properties", ["city_id"])


def downgrade() -> None:
    op.drop_index("ix_properties_city_id", table_name="properties")
    op.drop_index("ix_properties_branch_id", table_name="properties")
    op.drop_index("ix_properties_parent_property_id", table_name="properties")
    op.drop_column("properties", "maid_room")
    op.drop_column("properties", "swimming_pool")
    op.drop_column("properties", "garden")
    op.drop_column("properties", "parking_spaces_count")
    op.drop_column("properties", "elevators")
