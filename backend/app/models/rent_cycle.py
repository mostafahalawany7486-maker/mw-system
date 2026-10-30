"""
Rent Cycle Engine module (Phase 14).

Business context: today, rent invoices are generated one billing period
at a time via FinancialService.generate_bulk_invoices() (Rent Billing
Engine, Phase 8/10) and printable pre-payment receipts are generated via
RentalService.generate_monthly_receipts() (Rental Receipt Module, Phase
7). Both are correct, working, and untouched by this phase. What did
NOT exist is a single entity that represents "the monthly rent cycle"
itself — something with its own lifecycle (Draft -> Generated -> ... ->
Closed) that a branch manager can look at to answer "did we run this
month's rent cycle yet, and how far along is collection". RentCycle is
that entity: a thin orchestration/reporting layer OVER the two existing
engines, not a replacement for either.

RentCycle does not duplicate the Invoice or RentalPaymentInstallment
tables, and does not touch rental_contracts / lease_agreements. It
references them read-only:
  - RentCycleRecord.rental_contract_id -> the lease this record covers.
  - RentCycleRecord.invoice_id         -> the Rent Billing Engine Invoice
    generated for it this cycle (nullable until generation runs).
  - RentCycleRecord.installment_id     -> the RentalPaymentInstallment
    whose receipt_number was assigned this cycle (nullable until the
    receipt step runs).

One RentCycleRecord per (cycle, rental_contract) — this is what makes
"prevent duplicate generation" enforceable at the database level (see
the unique constraint below), on top of the idempotency
generate_bulk_invoices/generate_monthly_receipts already provide.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, DateTime, Text, Numeric, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class RentCycleStatus:
    DRAFT = "draft"
    GENERATED = "generated"
    PRINTED = "printed"
    DISTRIBUTED = "distributed"
    COLLECTING = "collecting"
    PARTIALLY_COLLECTED = "partially_collected"
    COMPLETED = "completed"
    CLOSED = "closed"
    CANCELLED = "cancelled"

    # Terminal states a cycle can never leave.
    TERMINAL = {CLOSED, CANCELLED}


class RentCycleRecordStatus:
    GENERATED = "generated"   # invoice + receipt successfully created for this lease this cycle
    SKIPPED = "skipped"       # lease was not eligible (not active / outside term) at generation time
    FAILED = "failed"         # generation was attempted but the underlying engine call raised


class RentCycle(BaseModel):
    __tablename__ = "rent_cycles"

    cycle_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    closing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    cycle_status: Mapped[str] = mapped_column(String(30), default=RentCycleStatus.DRAFT, index=True)

    # Optional portfolio scoping (mirrors generate_bulk_invoices'
    # property_ids param) — None means "every active contract".
    property_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    records: Mapped[list["RentCycleRecord"]] = relationship(
        back_populates="cycle", cascade="all, delete-orphan", order_by="RentCycleRecord.id"
    )

    @property
    def is_regenerable(self) -> bool:
        return self.cycle_status not in RentCycleStatus.TERMINAL


class RentCycleRecord(BaseModel):
    __tablename__ = "rent_cycle_records"
    __table_args__ = (
        UniqueConstraint("cycle_id", "rental_contract_id", name="uq_rent_cycle_record_cycle_contract"),
    )

    cycle_id: Mapped[int] = mapped_column(ForeignKey("rent_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    rental_contract_id: Mapped[int] = mapped_column(ForeignKey("rental_contracts.id"), nullable=False, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    installment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_payment_installments.id"), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    record_status: Mapped[str] = mapped_column(String(20), default=RentCycleRecordStatus.GENERATED, index=True)
    skip_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cycle: Mapped["RentCycle"] = relationship(back_populates="records")
    rental_contract: Mapped["RentalContract"] = relationship(foreign_keys=[rental_contract_id])  # noqa: F821
    invoice: Mapped[Optional["Invoice"]] = relationship(foreign_keys=[invoice_id])  # noqa: F821
    installment: Mapped[Optional["RentalPaymentInstallment"]] = relationship(foreign_keys=[installment_id])  # noqa: F821

    # ---- Read-only display fields, mirroring the same pattern already
    # used by MaintenanceRequest (tenant_display_name/property_title/
    # contractor_name) and RentalContract (tenant_display_name) — these
    # never denormalize data into stored columns, just surface it for
    # API responses via the existing relationships.
    @property
    def tenant_display_name(self) -> Optional[str]:
        contract = self.rental_contract
        return contract.tenant.display_name if contract and contract.tenant else None

    @property
    def property_title(self) -> Optional[str]:
        contract = self.rental_contract
        return contract.property_ref.title if contract and contract.property_ref else None

    @property
    def building_title(self) -> Optional[str]:
        contract = self.rental_contract
        if contract and contract.property_ref and contract.property_ref.parent:
            return contract.property_ref.parent.title
        return None

    @property
    def unit_number(self) -> Optional[str]:
        contract = self.rental_contract
        return contract.property_ref.unit_number if contract and contract.property_ref else None

    @property
    def invoice_number(self) -> Optional[str]:
        return self.invoice.invoice_number if self.invoice else None

    @property
    def invoice_status(self) -> Optional[str]:
        return self.invoice.invoice_status if self.invoice else None

    @property
    def receipt_number(self) -> Optional[str]:
        return self.installment.receipt_number if self.installment else None
