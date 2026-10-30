"""
Rental Contracts module (Phase 7) — the contract between the company and a
Tenant (the company SUBLEASES the property TO the tenant; see business
model). This is the final link in the chain: Owner -> Lease Agreement ->
Company -> Rental Contract -> Tenant.

Deliberately mirrors LeaseAgreement (Phase 3) structurally — same status
machine, same renewal-creates-a-new-row pattern, same on-demand maintenance
sweep for reminders/overdue flags — since a rental contract IS a lease
contract in shape, just on the other side of the business. It's kept as a
separate model (not a shared base/mixin) because the two are governed by
different rules going forward (e.g. late fees, discounts, and taxes are
tenant-facing concepts that make no sense on the owner side).

"Property" and "Unit" from the spec are the same field here: a rental
contract references the specific unit-level Property record (which may
itself have a parent Building via Property.parent_property_id, per Phase
4/5). There's no separate unit_id — that would just duplicate property_id.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Date, Text, Numeric, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class RentalContractStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    RENEWED = "renewed"


class RentalPaymentFrequency:
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    ONE_TIME = "one_time"
    CUSTOM = "custom"


class RentalSecurityDepositStatus:
    HELD = "held"
    RETURNED = "returned"
    PARTIALLY_RETURNED = "partially_returned"
    FORFEITED = "forfeited"


class RentalInstallmentStatus:
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class DiscountType:
    NONE = "none"
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class LateFeeType:
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class RentalContract(BaseModel):
    __tablename__ = "rental_contracts"

    contract_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    signed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    is_renewable: Mapped[bool] = mapped_column(Boolean, default=True)
    renewal_notice_days: Mapped[int] = mapped_column(Integer, default=30)
    renewal_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    # Confirmed directly: tenant contracts specifically (not Master
    # Leases with owners — those are untouched) should be able to renew
    # themselves automatically with no reminder notification needed,
    # per-contract rather than a global switch (a discount/late-fee
    # negotiation, a tenant moving out, etc. can all mean a specific
    # contract shouldn't auto-renew even if most do). False by default
    # — every existing contract keeps today's manual-renewal-with-
    # reminder behavior unless this is explicitly turned on for it.
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    renewed_from_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_contracts.id"), nullable=True)

    payment_frequency: Mapped[str] = mapped_column(String(20), default=RentalPaymentFrequency.MONTHLY)
    rent_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("currencies.id"), nullable=True)

    security_deposit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    security_deposit_status: Mapped[str] = mapped_column(String(20), default=RentalSecurityDepositStatus.HELD)

    # --- Discounts ---
    discount_type: Mapped[str] = mapped_column(String(20), default=DiscountType.NONE)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)  # percentage (0-100) or fixed amount, per discount_type
    discount_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Taxes ---
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)  # percentage, e.g. 5.00 for 5% VAT

    # --- Late Fees ---
    late_fee_type: Mapped[str] = mapped_column(String(20), default=LateFeeType.FIXED)
    late_fee_value: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    late_fee_grace_period_days: Mapped[int] = mapped_column(Integer, default=5)

    contract_status: Mapped[str] = mapped_column(String(20), default=RentalContractStatus.DRAFT, index=True)
    terminated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Phase 18 (Occupancy Engine) — distinguishes "tenant has formally
    # given notice" (Notice Period) from "contract is simply approaching
    # end_date" (Vacating Soon, derived from is_expiring_soon below).
    # Nullable/optional: most contracts run to natural expiry without
    # anyone ever setting this.
    move_out_notice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    notes_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(foreign_keys=[tenant_id])  # noqa: F821
    property_ref: Mapped["Property"] = relationship(foreign_keys=[property_id])  # noqa: F821
    installments: Mapped[list["RentalPaymentInstallment"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="RentalPaymentInstallment.due_date"
    )
    renewed_from: Mapped[Optional["RentalContract"]] = relationship(remote_side="RentalContract.id", foreign_keys=[renewed_from_contract_id])

    @property
    def is_expiring_soon(self) -> bool:
        if self.contract_status != RentalContractStatus.ACTIVE:
            return False
        days_remaining = (self.end_date - date.today()).days
        return 0 <= days_remaining <= self.renewal_notice_days

    @property
    def days_until_expiry(self) -> int:
        return (self.end_date - date.today()).days

    @property
    def tenant_display_name(self) -> Optional[str]:
        return self.tenant.display_name if self.tenant else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def unit_number(self) -> Optional[str]:
        return self.property_ref.unit_number if self.property_ref else None

    @property
    def discount_amount_computed(self) -> Decimal:
        """Discount applied to a single rent installment, based on discount_type."""
        if self.discount_type == DiscountType.PERCENTAGE:
            return (self.rent_amount * self.discount_value / Decimal("100")).quantize(Decimal("0.01"))
        if self.discount_type == DiscountType.FIXED:
            return self.discount_value
        return Decimal("0")

    @property
    def tax_amount_computed(self) -> Decimal:
        """Tax applied to a single rent installment (after discount)."""
        taxable = self.rent_amount - self.discount_amount_computed
        return (taxable * self.tax_rate / Decimal("100")).quantize(Decimal("0.01"))


class RentalPaymentInstallment(BaseModel):
    __tablename__ = "rental_payment_installments"

    contract_id: Mapped[int] = mapped_column(ForeignKey("rental_contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)  # base rent amount for this installment
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    late_fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    payment_status: Mapped[str] = mapped_column(String(20), default=RentalInstallmentStatus.PENDING, index=True)
    paid_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Rental Receipt Module: this row already represents "one month's
    # rent obligation for one contract" — the receipt_number/printed_at/
    # print_count fields turn it into the backing record for a printable
    # monthly receipt too, issued before payment (payment_status stays
    # whatever it already was; printing never changes it).
    receipt_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    print_count: Mapped[int] = mapped_column(Integer, default=0)

    contract: Mapped["RentalContract"] = relationship(back_populates="installments", foreign_keys=[contract_id])

    @property
    def total_payable(self) -> Decimal:
        return self.amount - self.discount_amount + self.tax_amount + self.late_fee_amount

    @property
    def is_overdue(self) -> bool:
        return self.payment_status == RentalInstallmentStatus.PENDING and self.due_date < date.today()
