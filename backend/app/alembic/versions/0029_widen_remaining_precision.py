"""Widen the 4 remaining financial Numeric(10, 2) columns to 3 decimals

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-29

0028 widened every Numeric(14, 2) / Numeric(12, 2) financial column to
3 decimals (KWD fils) — but it was built by grepping specifically for
those two precisions, and these 4 columns used a THIRD precision,
Numeric(10, 2), so they weren't caught: Contractor.hourly_rate,
Technician.hourly_rate, MaintenanceMaterial.unit_cost, and
MaintenanceLaborCost.hourly_rate. All four are genuine currency
amounts (KWD/hour, KWD per material unit) that were still silently
rounding away any fils entered.

SAFE, NON-DESTRUCTIVE, same as 0028: this only WIDENS precision
(2 -> 3 decimals). An existing value like 15.00 is unaffected. No
existing data is rounded, truncated, or lost.

MaintenanceMaterial.quantity (also Numeric(10, 2), same table) is
deliberately NOT included — it's a unit count (e.g. "5 bags of
cement"), not a currency amount, and has nothing to do with KWD fils.
Property.area_sqm (also Numeric(10, 2)) is deliberately NOT included
for the same reason — square meters, not currency.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels = None
depends_on = None

COLUMNS = [
    ("contractors", "hourly_rate"),
    ("technicians", "hourly_rate"),
    ("maintenance_materials", "unit_cost"),
    ("maintenance_labor_costs", "hourly_rate"),
]


def upgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(table, column, type_=sa.Numeric(10, 3), existing_type=sa.Numeric(10, 2))


def downgrade() -> None:
    # Best-effort only — narrowing 3 decimals back to 2 rounds away any
    # fils-level data entered after the upgrade, same caveat as 0028.
    for table, column in COLUMNS:
        op.alter_column(table, column, type_=sa.Numeric(10, 2), existing_type=sa.Numeric(10, 3))
