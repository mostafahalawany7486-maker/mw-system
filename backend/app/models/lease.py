"""
Lease Agreements module (Phase 3) — the contract between the company and a
Property Owner (the company LEASES FROM the owner; see business model).
This is the second link in the chain: Owner -> Lease Agreement -> Company
-> (future) Sublease -> Tenant.

Note: a formal Property entity does not exist yet (not built in Phase 1/2).
`property_reference` is a free-text description of the leased property/unit
for now; once a Properties module is built, add a nullable `property_id` FK
here and backfill — this table is deliberately structured so that's an
additive change, not a rewrite.
"""
from datetime import date
from typing import Optional
from decimal import Decimal
from sqlalchemy import String, ForeignKey, Boolean, Date, Text, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class LeaseStatus:
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    RENEWED = "renewed"


class PaymentFrequency:
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    ONE_TIME = "one_time"
    CUSTOM = "custom"


class SecurityDepositStatus:
    HELD = "held"
    RETURNED = "returned"
    PARTIALLY_RETURNED = "partially_returned"
    FORFEITED = "forfeited"


class InstallmentStatus:
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class LeaseAgreement(BaseModel):
    __tablename__ = "lease_agreements"

    contract_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"), nullable=False, index=True)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)

    property_reference: Mapped[str] = mapped_column(Text, nullable=False)  # free-text until Properties module exists

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    signed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    is_renewable: Mapped[bool] = mapped_column(Boolean, default=True)
    renewal_notice_days: Mapped[int] = mapped_column(Integer, default=30)
    renewal_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    renewed_from_lease_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lease_agreements.id"), nullable=True)

    payment_frequency: Mapped[str] = mapped_column(String(20), default=PaymentFrequency.MONTHLY)
    rent_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("currencies.id"), nullable=True)

    security_deposit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    security_deposit_status: Mapped[str] = mapped_column(String(20), default=SecurityDepositStatus.HELD)

    contract_status: Mapped[str] = mapped_column(String(20), default=LeaseStatus.DRAFT, index=True)
    terminated_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    notes_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owner: Mapped["Owner"] = relationship(foreign_keys=[owner_id])  # noqa: F821
    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821
    installments: Mapped[list["LeasePaymentInstallment"]] = relationship(
        back_populates="lease", cascade="all, delete-orphan", order_by="LeasePaymentInstallment.due_date"
    )
    renewed_from: Mapped[Optional["LeaseAgreement"]] = relationship(remote_side="LeaseAgreement.id", foreign_keys=[renewed_from_lease_id])

    @property
    def is_expiring_soon(self) -> bool:
        if self.contract_status != LeaseStatus.ACTIVE:
            return False
        days_remaining = (self.end_date - date.today()).days
        return 0 <= days_remaining <= self.renewal_notice_days

    @property
    def days_until_expiry(self) -> int:
        return (self.end_date - date.today()).days

    @property
    def owner_display_name(self) -> Optional[str]:
        return self.owner.display_name if self.owner else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def unit_number(self) -> Optional[str]:
        return self.property_ref.unit_number if self.property_ref else None


class LeasePaymentInstallment(BaseModel):
    __tablename__ = "lease_payment_installments"

    lease_id: Mapped[int] = mapped_column(ForeignKey("lease_agreements.id", ondelete="CASCADE"), nullable=False, index=True)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default=InstallmentStatus.PENDING, index=True)
    paid_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    lease: Mapped["LeaseAgreement"] = relationship(back_populates="installments", foreign_keys=[lease_id])

    @property
    def is_overdue(self) -> bool:
        return self.payment_status == InstallmentStatus.PENDING and self.due_date < date.today()
