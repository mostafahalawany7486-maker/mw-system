"""
Owner Ledger & Recoverable Expense Engine (Phase 17).

Pre-implementation analysis (see docs/owner-ledger-engine.md for the
full write-up, including the conflicts this phase's required analysis
found and how each was resolved):

  - The company already pays owners via LeaseAgreement/
    LeasePaymentInstallment + OwnerSettlementWorkflowService (Phase 12,
    app/business_workflows/owner_settlement_workflow_service.py) —
    that flow is NOT replaced. It has no concept of a running owner
    balance or of company-paid, owner-recoverable expenses, which is
    exactly the gap this phase fills.
  - "Recoverable expense" money still needs to hit the real ledger
    (Transaction -> JournalEntry, for "Accounting integration remains
    compatible") but must NEVER be classified as a company operating
    expense (spec: "This is NOT a normal company expense"). The
    existing `TransactionType.EXPENSE` is exactly that — a genuine
    operating expense — so two new, additive TransactionType values
    were added (RECOVERABLE_EXPENSE, OWNER_REIMBURSEMENT — see
    app/models/financial.py) rather than overloading EXPENSE/INCOME.
    This was the one existing file this phase needed to touch, and the
    change is purely additive: two new enum members, nothing removed
    or renamed, and PostingRule matching already degrades gracefully
    for unmapped transaction types (see
    JournalEntryService.auto_post_from_transaction), so nothing breaks
    for existing types.
  - This is the second sub-package (after rent_cycle/, Phase 14, and
    payment/, Phase 16) that owns its own SQLAlchemy model rather than
    being pure orchestration — an owner's running balance is itself a
    first-class ledger, not just an orchestration of others. See
    app/business_workflows/__init__.py's docstring for why that's a
    deliberate, narrow exception.

No existing table is modified. `owner_ledger_entries` is one new,
append-only table — spec: "No transaction can be deleted. Only
reversal entries are allowed." There is deliberately no delete/update
path anywhere in this module for a posted entry; see
owner_ledger_service.py's reverse_entry().
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, Text, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class OwnerLedgerTransactionType:
    RENTAL_INCOME = "rental_income"
    MANAGEMENT_FEE = "management_fee"
    MAINTENANCE_EXPENSE = "maintenance_expense"
    RECOVERABLE_EXPENSE = "recoverable_expense"
    RECOVERED_AMOUNT = "recovered_amount"
    OWNER_PAYMENT = "owner_payment"
    ADJUSTMENT = "adjustment"
    OPENING_BALANCE = "opening_balance"
    CLOSING_BALANCE = "closing_balance"

    ALL = {
        RENTAL_INCOME, MANAGEMENT_FEE, MAINTENANCE_EXPENSE, RECOVERABLE_EXPENSE, RECOVERED_AMOUNT,
        OWNER_PAYMENT, ADJUSTMENT, OPENING_BALANCE, CLOSING_BALANCE,
    }
    # Which types INCREASE the running balance (money the company owes
    # the owner) vs DECREASE it (money the owner owes the company, or
    # cash paid out) — see owner_ledger_service.py's post_entry(), the
    # one place this convention is applied. ADJUSTMENT is intentionally
    # absent: its direction is decided per-entry by the caller (it can
    # go either way), not fixed by type.
    CREDIT_TYPES = {RENTAL_INCOME, RECOVERED_AMOUNT, OPENING_BALANCE}
    DEBIT_TYPES = {MANAGEMENT_FEE, MAINTENANCE_EXPENSE, RECOVERABLE_EXPENSE, OWNER_PAYMENT}


class OwnerLedgerEntryStatus:
    ACTIVE = "active"
    REVERSED = "reversed"   # this entry has since been reversed by a later entry
    REVERSAL = "reversal"   # this entry IS a reversal of an earlier one


class OwnerLedgerEntry(BaseModel):
    """One row per financial movement affecting what the company
    currently owes (or is owed by) a given owner. Append-only: rows are
    never updated or deleted after creation except for the two
    self-referential reversal-linkage columns (reversal_of_id /
    reversed_by_id), which point sideways, not to changing this row's
    own financial effect.
    """
    __tablename__ = "owner_ledger_entries"

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)

    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    expense_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. "municipality_fees" — only meaningful for RECOVERABLE_EXPENSE

    # Polymorphic pointer to whatever produced this entry (a Transaction,
    # a MaintenanceRequest, a LeasePaymentInstallment, or "manual") — not
    # a foreign key, same deliberate pattern as ActivityLog.entity_id /
    # JournalEntry.source_transaction_id elsewhere in this codebase,
    # since the source table varies per entry.
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    # Running balance AFTER this entry is applied. Stored, not computed
    # live — safe and always correct precisely because the ledger is
    # append-only (see class docstring): a past entry's balance can
    # never be invalidated by a later event, only a reversal, which
    # itself always appends forward (see owner_ledger_service.py).
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    entry_status: Mapped[str] = mapped_column(String(20), default=OwnerLedgerEntryStatus.ACTIVE, index=True)
    reversal_of_id: Mapped[Optional[int]] = mapped_column(ForeignKey("owner_ledger_entries.id"), nullable=True)
    reversed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("owner_ledger_entries.id"), nullable=True)

    owner: Mapped["Owner"] = relationship(foreign_keys=[owner_id])  # noqa: F821
    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821

    @property
    def owner_name(self) -> Optional[str]:
        return self.owner.display_name if self.owner else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def building(self):
        return self.property_ref.parent if (self.property_ref and self.property_ref.parent) else None

    @property
    def building_id(self) -> Optional[int]:
        return self.building.id if self.building else None

    @property
    def building_name(self) -> Optional[str]:
        return self.building.title if self.building else None
