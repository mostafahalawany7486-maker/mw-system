"""
Payment & Collection Engine module (Phase 16).

Pre-implementation analysis (see docs/payment-collection-engine.md for
the full write-up — including the one real architectural conflict this
phase found and how it was resolved):

  - The system already records tenant payments today via
    FinancialService.create_transaction() (transaction_type=
    tenant_payment) — that mechanism is NOT replaced. `Payment` here is
    a front-door, two-phase (Pending -> Verified) wrapper around it: a
    payment is *captured* first (Pending), then *verified* — which is
    the point it actually posts to the ledger by calling the existing,
    unmodified FinancialService.record_invoice_payment() per allocated
    Invoice. This adds the genuinely new capability the spec asks for
    (a verification step before a captured payment counts as
    collected, plus a real "Refund"/"Reversal" lifecycle) without
    duplicating or reimplementing invoice payment, receipt issuance,
    or GL posting — all of that still happens in exactly one place.
  - "Receipt" in this Payment entity's `receipt_id` field, and every
    PaymentAllocation, means the Rent Billing Engine `Invoice` (Phase
    8/10) — NOT the older Rental Receipt Module's
    RentalPaymentInstallment ("RR-" numbered). Invoice already has a
    correct, existing partial-payment model (`amount_paid` accumulates,
    status becomes PARTIALLY_PAID vs PAID) that the older
    installment/receipt engine does not (its `create_transaction` sync
    always marks an installment fully "paid", full stop). Building a
    partial-payment-capable engine on top of the installment model
    would require changing that shared sync logic — which risks
    breaking every other existing caller of create_transaction, which
    the rules explicitly prohibit. Building it on Invoice instead needs
    zero changes to any existing file. This is the one real conflict
    the spec's own analysis step was meant to surface.
  - Owner-side amounts are intentionally read-only display fields here
    (see Payment.owner_id/.owner_name below) — no owner payout/
    settlement logic is implemented in this phase, per the spec's own
    explicit "Do not implement Owner Accounting in this phase."

No existing table is modified. `payments`/`payment_allocations` are two
new tables; they reference `tenants`, `properties`, `rental_contracts`,
`invoices`, `financial_accounts`, and `transactions` read-only via
foreign keys, the same "reference, never duplicate" pattern already
used by RentCycleRecord (Phase 14) and RentVoucher (Phase 15).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, DateTime, Text, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class PaymentMethod:
    CASH = "cash"
    KNET = "knet"
    BANK_TRANSFER = "bank_transfer"
    CHEQUE = "cheque"
    ONLINE = "online"
    MIXED = "mixed"  # Payment-level only — see payment_validator.py


class PaymentStatus:
    PENDING = "pending"
    VERIFIED = "verified"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    REVERSED = "reversed"

    TERMINAL = {CANCELLED, REFUNDED, REVERSED}


class Payment(BaseModel):
    __tablename__ = "payments"

    payment_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    rental_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_contracts.id"), nullable=True, index=True)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"), nullable=False)

    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    payment_status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING, index=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refund_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(foreign_keys=[tenant_id])  # noqa: F821
    rental_contract: Mapped[Optional["RentalContract"]] = relationship(foreign_keys=[rental_contract_id])  # noqa: F821
    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821
    account: Mapped["FinancialAccount"] = relationship(foreign_keys=[account_id])  # noqa: F821
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", order_by="PaymentAllocation.id"
    )

    # ---- Read-only display fields — same pattern as RentCycleRecord/
    # RentVoucher: never a stored/duplicated column.
    @property
    def tenant_name(self) -> Optional[str]:
        return self.tenant.display_name if self.tenant else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def building(self):
        return self.property_ref.parent if (self.property_ref and self.property_ref.parent) else None

    @property
    def building_name(self) -> Optional[str]:
        return self.building.title if self.building else None

    @property
    def owner_id(self) -> Optional[int]:
        """Read-only reference — see the module docstring: this phase
        does not implement Owner Accounting, so this is display-only
        and never drives any owner-side business logic."""
        return self.property_ref.owner_id if self.property_ref else None

    @property
    def owner_name(self) -> Optional[str]:
        owner = self.property_ref.owner if (self.property_ref and self.property_ref.owner) else None
        return owner.display_name if owner else None

    @property
    def is_reversible(self) -> bool:
        return self.payment_status not in PaymentStatus.TERMINAL and self.payment_status != PaymentStatus.PENDING


class PaymentAllocation(BaseModel):
    """One row per Invoice a Payment covers — this is what makes 'one
    payment covering multiple receipts' (per spec) possible: a single
    Payment can have N allocations across N different Invoices, each
    with its own amount. See payment_allocator.py."""
    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_payment_invoice"),
    )

    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    # Set once verify() actually posts this allocation via
    # FinancialService.record_invoice_payment — nullable until then.
    transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True)

    payment: Mapped["Payment"] = relationship(back_populates="allocations")
    invoice: Mapped["Invoice"] = relationship(foreign_keys=[invoice_id])  # noqa: F821
    transaction: Mapped[Optional["Transaction"]] = relationship(foreign_keys=[transaction_id])  # noqa: F821

    @property
    def invoice_number(self) -> Optional[str]:
        return self.invoice.invoice_number if self.invoice else None
