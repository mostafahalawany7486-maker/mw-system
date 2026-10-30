"""
owner_statement_service.py

Generates the professional Owner Statement the spec asks for: Opening
Balance, Rental Income, Management Fees, Recoverable Expenses,
Recovered Amounts, Other Adjustments, Net Balance, Closing Balance —
plus an extra "Owner Payments" line (not in the spec's minimum list,
but a real owner statement needs it, and the spec's wording is "must
include" a set, not "must be limited to" it) and the full list of line
items in the period.

Purely a read/aggregation layer over OwnerLedgerRepository — posts
nothing, computes nothing that owner_ledger_service.py's stored running
balance doesn't already make trivial to read.
"""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.owner_ledger import OwnerLedgerTransactionType
from app.repositories.owner_ledger_repository import OwnerLedgerRepository
from app.business_workflows.owner_ledger.owner_ledger_validator import OwnerLedgerValidator


class OwnerStatementService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OwnerLedgerRepository(db)
        self.validator = OwnerLedgerValidator(db)

    def generate_statement(self, owner_id: int, date_from: date, date_to: date) -> dict:
        owner = self.validator.validate_owner(owner_id)

        opening_balance = self.repo.balance_before(owner_id, date_from)
        line_items = self.repo.list_in_range(owner_id, date_from, date_to)

        def net_for(transaction_type: str, credit_positive: bool = True) -> Decimal:
            totals = self.repo.sum_by_type_in_range(owner_id, transaction_type, date_from, date_to)
            return (totals["credit"] - totals["debit"]) if credit_positive else (totals["debit"] - totals["credit"])

        rental_income = net_for(OwnerLedgerTransactionType.RENTAL_INCOME)
        management_fees = net_for(OwnerLedgerTransactionType.MANAGEMENT_FEE, credit_positive=False)
        recoverable_expenses = net_for(OwnerLedgerTransactionType.RECOVERABLE_EXPENSE, credit_positive=False)
        recovered_amounts = net_for(OwnerLedgerTransactionType.RECOVERED_AMOUNT)
        owner_payments = net_for(OwnerLedgerTransactionType.OWNER_PAYMENT, credit_positive=False)

        adjustment_totals = self.repo.sum_by_type_in_range(owner_id, OwnerLedgerTransactionType.ADJUSTMENT, date_from, date_to)
        other_adjustments = adjustment_totals["credit"] - adjustment_totals["debit"]

        net_movement = (
            rental_income - management_fees - recoverable_expenses + recovered_amounts
            - owner_payments + other_adjustments
        )
        closing_balance = opening_balance + net_movement

        return {
            "owner_id": owner_id,
            "owner_name": owner.display_name if owner else None,
            "date_from": date_from,
            "date_to": date_to,
            "opening_balance": opening_balance,
            "rental_income": rental_income,
            "management_fees": management_fees,
            "recoverable_expenses": recoverable_expenses,
            "recovered_amounts": recovered_amounts,
            "owner_payments": owner_payments,
            "other_adjustments": other_adjustments,
            "net_movement": net_movement,
            "closing_balance": closing_balance,
            "line_items": line_items,
        }
