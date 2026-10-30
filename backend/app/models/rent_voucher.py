"""
Rent Voucher Printing module (Phase 15).

Pre-implementation analysis (see docs/rent-voucher-module.md for the
full write-up):

  - The rental payment side already exists in full: Transaction
    (app/models/financial.py, transaction_type=tenant_payment) is the
    payment record; RentalPaymentInstallment already has its own
    "Rental Receipt Module" (RR-numbered, print_count/printed_at,
    Arabic+English amount-in-words via app/core/number_to_words.py).
  - This module does NOT replace or duplicate that receipt. A "Rent
    Voucher" here is a distinct, explicitly two-copy (Tenant Copy /
    Company Copy) filing document tied directly to a Transaction, with
    its own numbering, its own barcode, and its own print/reprint
    history — the spec is explicit that this is a *new* document type,
    not a reskin of the existing receipt.
  - Printing in this codebase is already browser-driven, not
    server-PDF-driven: every existing printable document
    (RentalService.get_receipt_document, FinancialService's invoice
    print DTOs) returns a plain dict; the frontend renders the actual
    print layout and calls the browser's native print dialog, then
    tells the backend a print happened (record_print). RentVoucher
    follows the exact same contract — see rent_voucher_service.py for
    why this also happens to be the only safe way to get correct
    Arabic RTL shaping without adding a new server-side dependency.

This model does not touch or duplicate columns from Transaction,
RentalContract, Tenant, or Property — everything display-related is a
read-only computed property resolved through the existing
transaction_id relationship, same pattern as RentCycleRecord
(app/models/rent_cycle.py, Phase 14).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Date, DateTime, Text, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class VoucherCopyType:
    TENANT = "tenant"
    COMPANY = "company"


# Maps Transaction.payment_method (see VALID_PAYMENT_METHODS in
# app/schemas/financial.py / app/schemas/rental.py — "knet" already
# exists there, nothing added) onto the voucher's bilingual checkbox
# labels. Anything not explicitly listed (card, online, or unset)
# prints as "Other / أخرى" rather than being hidden.
PAYMENT_METHOD_LABELS = {
    "cash": ("Cash", "نقدي"),
    "bank_transfer": ("Bank Transfer", "تحويل بنكي"),
    "cheque": ("Cheque", "شيك"),
    "knet": ("K-Net", "كي نت"),
}
PAYMENT_METHOD_OTHER = ("Other", "أخرى")


class RentVoucher(BaseModel):
    __tablename__ = "rent_vouchers"
    __table_args__ = (
        UniqueConstraint("transaction_id", "copy_type", name="uq_rent_voucher_transaction_copy"),
    )

    voucher_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    copy_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rental_month: Mapped[date] = mapped_column(Date, nullable=False)

    barcode_value: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    print_count: Mapped[int] = mapped_column(Integer, default=0)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ---- Combined Voucher extension: lets one voucher cover several
    # months paid together (e.g. a tenant pays 3 months at once) instead
    # of forcing one voucher per transaction. `transaction_id` above
    # stays the single required FK (the first/primary transaction — the
    # UniqueConstraint(transaction_id, copy_type) still applies to it
    # unchanged), and any additional transactions being combined into
    # this same voucher are listed here as plain comma-separated IDs
    # rather than a new association table, since nothing else needs to
    # query "vouchers by extra transaction" — this is print-display-only
    # data. `combined_amount`, when set, is the total to print instead
    # of the primary transaction's own amount. Both stay NULL for the
    # (still default, still most common) one-transaction-per-voucher
    # case — nothing about that path changed.
    extra_transaction_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    combined_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)

    transaction: Mapped["Transaction"] = relationship(foreign_keys=[transaction_id])  # noqa: F821

    # ---- Read-only display fields, resolved through the transaction —
    # same "no denormalized columns, just properties over existing
    # relationships" pattern as RentCycleRecord (Phase 14) and
    # MaintenanceRequest's own display fields.
    @property
    def tenant(self):
        return self.transaction.tenant if self.transaction else None

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
    def unit(self):
        return self.transaction.property_ref if self.transaction else None

    @property
    def building(self):
        return self.unit.parent if (self.unit and self.unit.parent) else None

    @property
    def building_name(self) -> Optional[str]:
        return self.building.title if self.building else None

    @property
    def unit_number(self) -> Optional[str]:
        return (self.unit.unit_number or self.unit.property_code) if self.unit else None

    @property
    def floor_unit_numbers(self) -> Optional[str]:
        """When this voucher is for a "whole floor" contract (see
        PropertyService.get_or_create_floor_unit /
        RentalService._sync_floor_wide_overrides), lists every real
        unit's number on that floor — confirmed directly: the voucher
        for a whole-floor contract should show each unit number on it,
        not just the floor's own generic label. None for a normal
        single-unit voucher."""
        from app.models.property import PropertyType, Property as PropertyModel
        if not self.unit or self.unit.property_type != PropertyType.FLOOR or not self.unit.floor_id:
            return None
        from sqlalchemy.orm import object_session
        session = object_session(self)
        if not session:
            return None
        siblings = session.query(PropertyModel).filter(
            PropertyModel.floor_id == self.unit.floor_id, PropertyModel.deleted_at.is_(None),
            PropertyModel.property_type != PropertyType.FLOOR,
        ).order_by(PropertyModel.unit_number).all()
        numbers = [s.unit_number or s.property_code for s in siblings]
        return ", ".join(numbers) if numbers else None

    @property
    def unit_paci_number(self) -> Optional[str]:
        """The unit's own Kuwait PACI address code — NOT a personal ID,
        corrects an earlier mistake where this was sourced from the
        tenant's national_id instead. See docs/paci-number-correction.md."""
        return self.unit.paci_number if self.unit else None

    @property
    def property_address(self) -> Optional[str]:
        location = (self.building or self.unit)
        return location.display_location if location else None

    @property
    def amount(self):
        if self.combined_amount is not None:
            return self.combined_amount
        return self.transaction.amount if self.transaction else None

    @property
    def is_combined(self) -> bool:
        return bool(self.extra_transaction_ids)

    @property
    def combined_transaction_count(self) -> int:
        if not self.extra_transaction_ids:
            return 1
        return 1 + len([x for x in self.extra_transaction_ids.split(",") if x.strip()])

    @property
    def all_transaction_ids(self) -> list[int]:
        ids = [self.transaction_id]
        if self.extra_transaction_ids:
            ids += [int(x) for x in self.extra_transaction_ids.split(",") if x.strip()]
        return ids

    @property
    def payment_method(self) -> Optional[str]:
        return self.transaction.payment_method if self.transaction else None

    @property
    def payment_method_label_en(self) -> str:
        return PAYMENT_METHOD_LABELS.get(self.payment_method, PAYMENT_METHOD_OTHER)[0]

    @property
    def payment_method_label_ar(self) -> str:
        return PAYMENT_METHOD_LABELS.get(self.payment_method, PAYMENT_METHOD_OTHER)[1]

    @property
    def transaction_number(self) -> Optional[str]:
        return self.transaction.transaction_number if self.transaction else None
