"""
Pending Rent Slip — printed BEFORE collection, per the exact workflow
described in conversation: at the start of each month, print a slip
that looks and reads identically to a real Rent Voucher, hand it to
the building guard for the tenant; only when the guard later confirms
the tenant actually paid does the owner come back to the system and
confirm collection — at which point (and only then) the real
Transaction and the real RentVoucher pair (Phase 15/19, untouched by
this module) are created.

Deliberately a SEPARATE table from RentVoucher, not a new status on
it — RentVoucher's entire design guarantee is "a voucher only exists
because a real Transaction already exists" (see rent_voucher.py's own
docstring: "the spec is explicit this is tied directly to a
Transaction"). Loosening that guarantee to allow a transaction-less
voucher would weaken it for every existing caller. A pending slip is a
distinct, additive concept upstream of that guarantee, not a
loosening of it — nothing about RentVoucher, its uniqueness
constraint, or its generation logic is touched.

Mirrors RentVoucher's own computed-properties pattern (tenant_name,
building_name, etc. resolved live through relationships, not
denormalized columns) so the print DTO these slips produce can reuse
the exact same frontend rendering component as a real voucher, with
identical shape, dimensions, and content, per request.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, DateTime, Text, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel
from app.models.rent_voucher import PAYMENT_METHOD_LABELS, PAYMENT_METHOD_OTHER


class PendingRentSlipStatus:
    PENDING = "pending"
    COLLECTED = "collected"
    CANCELLED = "cancelled"


class PendingRentSlip(BaseModel):
    __tablename__ = "pending_rent_slips"
    __table_args__ = (
        UniqueConstraint("tenant_id", "property_id", "rental_month", "copy_type", name="uq_pending_slip_tenant_property_month_copy"),
    )

    slip_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False, index=True)
    copy_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # tenant / company — same pair-per-page pattern as RentVoucher
    rental_month: Mapped[date] = mapped_column(Date, nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    barcode_value: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # Named `slip_status` (not `status`) on purpose — BaseModel already
    # has its own `status` column for the shared active/archived
    # concept (see the Archive extension elsewhere in this codebase);
    # reusing that column for this slip's own pending/collected/
    # cancelled workflow would overload it with a second, conflicting
    # meaning.
    slip_status: Mapped[str] = mapped_column(String(20), default=PendingRentSlipStatus.PENDING, index=True)

    print_count: Mapped[int] = mapped_column(Integer, default=0)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Set only once collection is confirmed — the bridge into the real,
    # unmodified Transaction -> RentVoucher pipeline.
    collected_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(foreign_keys=[tenant_id])  # noqa: F821
    property_ref: Mapped["Property"] = relationship(foreign_keys=[property_id])  # noqa: F821
    collected_transaction: Mapped[Optional["Transaction"]] = relationship(foreign_keys=[collected_transaction_id])  # noqa: F821

    # ---- Read-only display fields — same shape as RentVoucher's own
    # computed properties, so both feed the identical print template.
    @property
    def tenant_name(self) -> Optional[str]:
        return self.tenant.display_name if self.tenant else None

    @property
    def tenant_code(self) -> Optional[str]:
        return self.tenant.tenant_code if self.tenant else None

    @property
    def tenant_national_id(self) -> Optional[str]:
        return self.tenant.national_id if self.tenant else None

    @property
    def tenant_phone(self) -> Optional[str]:
        return self.tenant.primary_phone if self.tenant else None

    @property
    def tenant_email(self) -> Optional[str]:
        return self.tenant.primary_email if self.tenant else None

    @property
    def building(self):
        return self.property_ref.parent if (self.property_ref and self.property_ref.parent) else None

    @property
    def building_name(self) -> Optional[str]:
        return self.building.title if self.building else (self.property_ref.title if self.property_ref else None)

    @property
    def unit_number(self) -> Optional[str]:
        return (self.property_ref.unit_number or self.property_ref.property_code) if self.property_ref else None

    @property
    def unit_paci_number(self) -> Optional[str]:
        """The unit's own Kuwait PACI address code — NOT a personal ID.
        See docs/paci-number-correction.md."""
        return self.property_ref.paci_number if self.property_ref else None

    @property
    def property_address(self) -> Optional[str]:
        location = (self.building or self.property_ref)
        return location.display_location if location else None

    @property
    def amount(self):
        return self.expected_amount

    # Deliberately always None until collected — an unpaid slip must
    # show every payment-method checkbox empty, exactly like a real
    # voucher whose transaction has no payment_method set yet.
    @property
    def payment_method(self) -> Optional[str]:
        return None

    @property
    def payment_method_label_en(self) -> str:
        return PAYMENT_METHOD_OTHER[0]

    @property
    def payment_method_label_ar(self) -> str:
        return PAYMENT_METHOD_OTHER[1]
