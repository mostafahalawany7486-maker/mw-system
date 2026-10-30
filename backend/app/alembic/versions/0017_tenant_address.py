"""Rental Receipt phase: Tenant address

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-19

Adds the one column the approved Rental Receipt design (Concept B —
Mirror Split) needs that didn't already exist: a printable Tenant
address. Free-text rather than a structured address_line1/city/country
breakdown like Property/Owner have, since it's only ever displayed as a
single printed line on a receipt, never filtered/searched/geocoded the
way property addresses are.
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "address")
