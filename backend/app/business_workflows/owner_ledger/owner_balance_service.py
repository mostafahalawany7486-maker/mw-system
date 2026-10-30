"""
owner_balance_service.py

Read-side queries over the ledger: current balance, outstanding
recoverable expenses, and the owner dashboard's monthly figures. Posts
nothing — every write happens in owner_ledger_service.py /
recoverable_expense_service.py / owner_settlement_service.py. Also
owns recompute_and_verify(), a consistency check (not used by any
write path) that recomputes the entire balance chain from scratch and
confirms it matches the stored `balance` column on every row — the
"Balance calculation" correctness check the spec's TESTING section
asks for, made explicit as its own reusable method rather than only
living inside a test.
"""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.owner_ledger import OwnerLedgerTransactionType
from app.repositories.owner_ledger_repository import OwnerLedgerRepository
from app.business_workflows.owner_ledger.owner_ledger_validator import OwnerLedgerValidator


class OwnerBalanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OwnerLedgerRepository(db)
        self.validator = OwnerLedgerValidator(db)

    def get_current_balance(self, owner_id: int) -> Decimal:
        self.validator.validate_owner(owner_id)
        last_entry = self.repo.get_last_entry(owner_id)
        return last_entry.balance if last_entry else Decimal("0")

    def get_outstanding_recoverable_expenses(self, owner_id: int) -> Decimal:
        self.validator.validate_owner(owner_id)
        return self.repo.sum_outstanding_recoverable(owner_id)

    def get_owner_balance_summary(self, owner_id: int) -> dict:
        return {
            "owner_id": owner_id,
            "current_balance": self.get_current_balance(owner_id),
            "outstanding_recoverable_expenses": self.get_outstanding_recoverable_expenses(owner_id),
        }

    def get_dashboard(self, owner_id: int) -> dict:
        self.validator.validate_owner(owner_id)
        today = date.today()
        month_start = today.replace(day=1)

        income_types = (OwnerLedgerTransactionType.RENTAL_INCOME,)
        expense_types = (
            OwnerLedgerTransactionType.MANAGEMENT_FEE, OwnerLedgerTransactionType.MAINTENANCE_EXPENSE,
            OwnerLedgerTransactionType.RECOVERABLE_EXPENSE,
        )

        monthly_income = Decimal("0")
        for t in income_types:
            totals = self.repo.sum_by_type_in_range(owner_id, t, month_start, today)
            monthly_income += totals["credit"] - totals["debit"]

        monthly_expenses = Decimal("0")
        for t in expense_types:
            totals = self.repo.sum_by_type_in_range(owner_id, t, month_start, today)
            monthly_expenses += totals["debit"] - totals["credit"]

        payments_made = self.repo.sum_by_type_in_range(owner_id, OwnerLedgerTransactionType.OWNER_PAYMENT, month_start, today)["debit"]
        payments_received = self.repo.sum_by_type_in_range(owner_id, OwnerLedgerTransactionType.RECOVERED_AMOUNT, month_start, today)["credit"]

        return {
            "owner_id": owner_id,
            "current_balance": self.get_current_balance(owner_id),
            "outstanding_recoverable_expenses": self.get_outstanding_recoverable_expenses(owner_id),
            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "payments_made": payments_made,
            "payments_received": payments_received,
        }

    def recompute_and_verify(self, owner_id: int) -> bool:
        """Walks every entry for the owner in insertion order and
        confirms the stored running balance matches what a from-scratch
        recomputation produces. Returns True if consistent. Does not
        write anything — a pure integrity check."""
        stmt_entries = self.repo.list_in_range(owner_id, date.min, date.max)
        # list_in_range orders by (transaction_date, id) — recomputation
        # must follow the same order post_entry() actually applied
        # entries in, which is insertion (id) order, since two entries
        # can share a transaction_date.
        entries = sorted(stmt_entries, key=lambda e: e.id)
        running = Decimal("0")
        for entry in entries:
            running += entry.credit - entry.debit
            if running != entry.balance:
                return False
        return True
