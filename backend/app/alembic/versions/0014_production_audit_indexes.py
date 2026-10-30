"""Production audit: add missing index on cities.country_id

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-18

Found during the production-readiness audit: every other foreign key
column in this codebase is indexed, but cities.country_id was missed —
despite being used to filter the country -> city cascading dropdown
(GET /cities?country_id=X, used throughout the Owner/Tenant/Property
address forms). Purely additive; no data touched.
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_cities_country_id", "cities", ["country_id"])


def downgrade() -> None:
    op.drop_index("ix_cities_country_id", table_name="cities")
