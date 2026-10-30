"""
Financial Engine (Phase 19).

Manages operational financial balances before accounting entries are
generated — accounting remains responsible only for journal entries and
the General Ledger (unchanged, Phase 10).

See docs/financial-engine.md for the full pre-implementation analysis.
The short version: almost everything this phase asks for already
existed somewhere (Transaction/FinancialAccount from Phase 8, Owner
Ledger from Phase 17, Payment Engine from Phase 16, deposit fields from
Phase 3/7) — building six separate physical ledger tables would have
meant six copies of data that could drift out of sync with each other,
which is the exact "ledger imbalance" the spec explicitly asks to
prevent. Instead:

  - Five of the six requested ledgers (Company, Owner, Tenant, Building,
    Property/Unit) are live VIEWS computed over existing tables —
    balance_service.py.
  - The one genuinely missing piece — a full Security Deposit lifecycle
    — is new: deposit_service.py + one new table, DepositLedgerEntry
    (app/models/financial_engine.py).
  - Refunds, allocations, and adjustments each reuse the existing Payment
    Engine / Owner Ledger rather than duplicating them —
    refund_service.py, allocation_service.py, adjustment_service.py.
  - "Accounting integration through events, never directly" is already
    how this codebase works: FinancialService.create_transaction()
    already triggers JournalEntryService.auto_post_from_transaction as a
    decoupled hook the Financial Engine never touches directly — see
    financial_transaction_service.py.

Module map:
  financial_engine.py               Facade — the one thing the API router calls
  balance_service.py                The six ledger views (five reused, one new-shaped)
  deposit_service.py                Security deposit lifecycle (the new piece)
  refund_service.py                 Tenant payment + deposit refunds
  adjustment_service.py             Owner + tenant manual adjustments
  allocation_service.py             Allocation validation, wraps the Payment Engine
  ledger_sync_service.py            Deposit ledger integrity check (not a real "sync" — see its own docstring)
  financial_transaction_service.py  Thin wrapper ensuring every movement is a real, auditable Transaction
  financial_validator.py            Every VALIDATIONS rule + this package's exceptions' home module
  financial_exceptions.py           This package's exceptions
"""
from app.business_workflows.financial_engine.financial_engine import FinancialEngine
from app.business_workflows.financial_engine.balance_service import BalanceService
from app.business_workflows.financial_engine.deposit_service import DepositService
from app.business_workflows.financial_engine.refund_service import RefundService
from app.business_workflows.financial_engine.adjustment_service import AdjustmentService
from app.business_workflows.financial_engine.allocation_service import AllocationService
from app.business_workflows.financial_engine.ledger_sync_service import LedgerSyncService
from app.business_workflows.financial_engine.financial_transaction_service import FinancialTransactionService
from app.business_workflows.financial_engine.financial_validator import FinancialValidator
from app.business_workflows.financial_engine.financial_exceptions import (
    FinancialEngineError, InvalidLedgerScopeError, EntityNotFoundError, DuplicateTransactionError,
    DuplicateDepositError, NegativeDepositError, OverRefundError, InvalidDepositTransitionError,
    InvalidAllocationError, LedgerImbalanceError, NegativeBalanceNotAllowedError,
)

__all__ = [
    "FinancialEngine", "BalanceService", "DepositService", "RefundService", "AdjustmentService",
    "AllocationService", "LedgerSyncService", "FinancialTransactionService", "FinancialValidator",
    "FinancialEngineError", "InvalidLedgerScopeError", "EntityNotFoundError", "DuplicateTransactionError",
    "DuplicateDepositError", "NegativeDepositError", "OverRefundError", "InvalidDepositTransitionError",
    "InvalidAllocationError", "LedgerImbalanceError", "NegativeBalanceNotAllowedError",
]
