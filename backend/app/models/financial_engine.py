"""
Financial Engine (Phase 19).

The one genuinely new table this phase needed. Every other "ledger" the
spec asks for is a live view over existing tables (see
business_workflows/financial_engine/balance_service.py's module
docstring) — but the Security Deposit lifecycle (Received / Held /
Partial Refund / Full Refund / Deduction / Forfeit / Transfer to Owner)
had nothing behind it at all: RentalContract.security_deposit_status
and LeaseAgreement.security_deposit_status (Phase 3/7) are single
fields with no service ever transitioning them (confirmed by grep
before writing any of this — the only existing reference,
lease_workflow_service.py, literally warns "settle it via the security
deposit workflow/endpoint" for a workflow that didn't exist yet).

A single amount+status field can't represent a real deposit's history
(received 1000, partially refunded 600, deducted 150 for damage,
forfeited the last 250) — hence DepositLedgerEntry: one append-only row
per action, so the full story is always reconstructable, not just the
current remainder.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Text, Numeric, Integer, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class DepositContractType:
    RENTAL = "rental"  # RentalContract (tenant <-> company)
    LEASE = "lease"    # LeaseAgreement (company <-> owner)
    ALL = [RENTAL, LEASE]


class DepositAction:
    RECEIVED = "received"
    PARTIAL_REFUND = "partial_refund"
    FULL_REFUND = "full_refund"
    DEDUCTION = "deduction"
    FORFEIT = "forfeit"
    TRANSFER_TO_OWNER = "transfer_to_owner"

    ALL = [RECEIVED, PARTIAL_REFUND, FULL_REFUND, DEDUCTION, FORFEIT, TRANSFER_TO_OWNER]
    # Actions that reduce the remaining held balance to zero — the
    # deposit is fully settled after any of these.
    TERMINAL = [FULL_REFUND, FORFEIT]


class DepositLedgerEntry(BaseModel):
    """One row per deposit lifecycle action. Append-only — matches
    every other financial history table in this codebase (OwnerLedgerEntry,
    OccupancyStatusHistory): nothing here is ever updated or deleted,
    only added to."""
    __tablename__ = "deposit_ledger_entries"

    contract_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    # Remaining held balance immediately AFTER this action — the same
    # "store the running total, not just the delta" convention
    # OwnerLedgerEntry.balance already established, for the same reason
    # (cheap, exact history reads without re-summing every time).
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # The real cash-movement record, when this action involves one
    # (received/refund/transfer_to_owner all do; a deduction for
    # damages does not — the cash was already in hand from RECEIVED,
    # so a deduction is bookkeeping, not a new cash movement — see
    # deposit_service.py for the full reasoning per action).
    transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transaction: Mapped[Optional["Transaction"]] = relationship(foreign_keys=[transaction_id])  # noqa: F821
