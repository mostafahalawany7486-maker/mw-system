"""
Owner Ledger & Recoverable Expense Engine (Phase 17).

Gives each owner a real, append-only running-balance ledger and a
first-class way to record company-paid expenses that are recoverable
from the owner — distinct from, and never classified as, a normal
company operating expense. See docs/owner-ledger-engine.md for the
full design write-up, including the conflicts this phase's required
analysis found and how each was resolved (new TransactionType values
instead of overloading EXPENSE/INCOME; a distinctly-named settlement
wrapper instead of colliding with the existing Phase 12
OwnerSettlementWorkflowService).

Like rent_cycle/ (Phase 14) and payment/ (Phase 16), this is a
sub-package that owns its own SQLAlchemy model
(app/models/owner_ledger.py: OwnerLedgerEntry) rather than being pure
orchestration — see app/business_workflows/__init__.py's docstring for
why that's a deliberate, narrow exception.

Module map:
  owner_ledger_service.py         Core append-only ledger: post / reverse
  recoverable_expense_service.py  Company-pays-on-owner's-behalf + reimbursement
  owner_balance_service.py        Balance/outstanding queries + dashboard
  owner_settlement_service.py     Ledger-aware wrapper over Phase 12's settlement
  owner_statement_service.py      Professional owner statement generation
  owner_ledger_validator.py       Every business rule + this package's exceptions
"""
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService
from app.business_workflows.owner_ledger.recoverable_expense_service import RecoverableExpenseService
from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
from app.business_workflows.owner_ledger.owner_settlement_service import OwnerLedgerSettlementService
from app.business_workflows.owner_ledger.owner_statement_service import OwnerStatementService
from app.business_workflows.owner_ledger.owner_ledger_validator import (
    OwnerLedgerValidator, OwnerLedgerError, OwnerNotFoundError, InvalidPropertyForOwnerError,
    NegativeAmountError, EntryNotFoundError, AlreadyReversedError, CannotReverseAReversalError,
)

__all__ = [
    "OwnerLedgerService",
    "RecoverableExpenseService",
    "OwnerBalanceService",
    "OwnerLedgerSettlementService",
    "OwnerStatementService",
    "OwnerLedgerValidator", "OwnerLedgerError", "OwnerNotFoundError", "InvalidPropertyForOwnerError",
    "NegativeAmountError", "EntryNotFoundError", "AlreadyReversedError", "CannotReverseAReversalError",
]
