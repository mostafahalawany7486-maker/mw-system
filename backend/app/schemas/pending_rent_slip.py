from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class GeneratePendingSlipsRequest(BaseModel):
    """One slip PAIR (tenant + company copy) per (tenant_id, property_id)
    entry — mirrors RentVoucher's generate-by-transaction shape, except
    there's no transaction yet, so the caller supplies tenant+property+
    expected amount directly instead."""
    rental_month: date
    entries: List["PendingSlipEntry"]


class PendingSlipEntry(BaseModel):
    tenant_id: int
    property_id: int
    expected_amount: Decimal


GeneratePendingSlipsRequest.model_rebuild()


class ConfirmCollectionRequest(BaseModel):
    """Confirms a pending slip PAIR was actually collected — creates the
    real Transaction (tenant_payment) and, from it, the real RentVoucher
    pair (Phase 15/19, untouched), exactly as if the payment had been
    recorded through Financial -> Record Transaction all along."""
    account_id: int
    payment_method: str
    payment_date: date
    reference_number: Optional[str] = None


class BulkSlipIdsRequest(BaseModel):
    slip_ids: List[int]


class PendingRentSlipListItemOut(BaseModel):
    id: int
    uuid: str
    created_at: datetime
    slip_number: str
    tenant_id: int
    tenant_name: Optional[str] = None
    tenant_code: Optional[str] = None
    property_id: int
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    copy_type: str
    rental_month: date
    expected_amount: Decimal
    slip_status: str
    collected_transaction_id: Optional[int] = None
    collected_at: Optional[datetime] = None
    print_count: int


class PendingRentSlipDashboardOut(BaseModel):
    total_slips: int
    pending_count: int
    collected_count: int
    cancelled_count: int


class PendingSlipPrintDataOut(BaseModel):
    """Deliberately the exact same field shape as RentVoucherPrintDataOut
    (app/schemas/rent_voucher.py) so the frontend can reuse the identical
    print component with zero visual difference, per request — payment
    fields are simply blank/unset here since nothing has been collected
    yet."""
    voucher_id: int  # the slip's own id, named to match the shared print component's prop
    voucher_number: str
    copy_type: str
    copy_type_label_en: str
    copy_type_label_ar: str

    issue_date: date
    rental_month_display_en: str
    rental_month_display_ar: str

    tenant_name: str
    tenant_code: Optional[str] = None
    tenant_national_id: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_email: Optional[str] = None

    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    unit_paci_number: Optional[str] = None
    property_address: Optional[str] = None

    amount: Decimal
    currency_code: Optional[str] = None
    amount_in_words_en: str
    amount_in_words_ar: str

    payment_method: Optional[str] = None
    payment_method_label_en: str
    payment_method_label_ar: str

    barcode_value: str
    print_count: int
    printed_at: Optional[datetime] = None
