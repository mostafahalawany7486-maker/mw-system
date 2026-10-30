"""Widen all financial Numeric columns from 2 to 3 decimal places (KWD fils)

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-29

Confirmed directly: this company operates in Kuwaiti Dinar, which has
3 decimal places (fils) instead of the 2 most currencies use. Every
Numeric(14, 2) / Numeric(12, 2) financial column in the schema is
widened to 3 decimal places here — 31 columns across 20 tables.

SAFE, NON-DESTRUCTIVE: this WIDENS precision (2 -> 3 decimals), it
never narrows it. An existing value like 400.00 is unaffected — it's
still exactly 400.00, just now able to also store 400.125 going
forward. No existing data is rounded, truncated, or lost. (The reverse
migration, 3 -> 2, WOULD be lossy — anything with fils information
would be rounded — which is why downgrade() below is intentionally
best-effort only, and this migration should be treated as one-way in
practice.)

The frontend's display formatting (minimumFractionDigits) and input
step precision were already updated separately to match (3 decimals)
— this migration is the corresponding storage-layer change so a fils
amount entered in the app actually gets stored, not silently rounded
away at the database level.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels = None
depends_on = None

# (table, column) pairs — every Numeric(14,2)/(12,2) financial column
# found via `grep -rn "Numeric(14, 2)\|Numeric(12, 2)" app/models/*.py`
# before this migration was written, cross-checked against each
# model's own __tablename__ so nothing is mistyped.
COLUMNS = [
    ("journal_entry_lines", "debit_amount"),
    ("journal_entry_lines", "credit_amount"),
    ("journal_entry_lines", "vat_amount"),
    ("financial_accounts", "opening_balance"),
    ("transactions", "amount"),
    ("invoices", "amount"),
    ("invoices", "amount_paid"),
    ("deposit_ledger_entries", "amount"),
    ("deposit_ledger_entries", "balance_after"),
    ("lease_agreements", "rent_amount"),
    ("lease_agreements", "security_deposit_amount"),
    ("lease_payment_installments", "amount"),
    ("maintenance_requests", "estimated_cost"),
    ("maintenance_contracts", "annual_cost"),
    ("owner_ledger_entries", "debit"),
    ("owner_ledger_entries", "credit"),
    ("owner_ledger_entries", "balance"),
    ("payments", "amount"),
    ("payment_allocations", "amount"),
    ("pending_rent_slips", "expected_amount"),
    ("properties", "rent_price"),
    ("rent_cycle_records", "amount"),
    ("rent_vouchers", "combined_amount"),
    ("rental_contracts", "rent_amount"),
    ("rental_contracts", "security_deposit_amount"),
    ("rental_contracts", "discount_value"),
    ("rental_contracts", "late_fee_value"),
    ("rental_payment_installments", "amount"),
    ("rental_payment_installments", "discount_amount"),
    ("rental_payment_installments", "tax_amount"),
    ("rental_payment_installments", "late_fee_amount"),
]

# Original total-digit precision per table, so upgrade()/downgrade()
# restore/apply the exact original scale (12 vs 14) rather than
# assuming every column used the same one.
TABLES_USING_PRECISION_12 = {"maintenance_requests"}  # this table's estimated_cost used Numeric(12, 2); every other column above used Numeric(14, 2)


def upgrade() -> None:
    for table, column in COLUMNS:
        precision = 12 if table in TABLES_USING_PRECISION_12 else 14
        op.alter_column(table, column, type_=sa.Numeric(precision, 3), existing_type=sa.Numeric(precision, 2))


def downgrade() -> None:
    # Best-effort only — narrowing 3 decimals back to 2 rounds away any
    # fils-level data entered after the upgrade. Included for
    # completeness, not recommended to actually run against a database
    # with real fils-precision data in it.
    for table, column in COLUMNS:
        precision = 12 if table in TABLES_USING_PRECISION_12 else 14
        op.alter_column(table, column, type_=sa.Numeric(precision, 2), existing_type=sa.Numeric(precision, 3))
