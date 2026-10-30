from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.schemas.common import AuditFieldsOut

VALID_COPY_TYPES = {"tenant", "company"}


class GenerateVouchersRequest(BaseModel):
    transaction_ids: List[int]
    rental_month: date
    # When True, ALL transaction_ids are combined into a single voucher
    # pair (one Tenant Copy + one Company Copy total, not one pair per
    # transaction) — e.g. a tenant paying 3 months at once. All listed
    # transactions must belong to the same tenant; the printed amount
    # is their sum and the printed period is a range starting at
    # rental_month spanning that many months. Default False keeps the
    # existing one-voucher-pair-per-transaction behavior unchanged.
    combine: bool = False

    @field_validator("transaction_ids")
    @classmethod
    def validate_non_empty(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("transaction_ids must include at least one transaction")
        return v


class RentVoucherOut(AuditFieldsOut):
    voucher_number: str
    transaction_id: int
    copy_type: str
    rental_month: date
    barcode_value: str
    print_count: int
    printed_at: Optional[datetime] = None

    tenant_name: Optional[str] = None
    tenant_code: Optional[str] = None
    tenant_phone: Optional[str] = None
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    unit_paci_number: Optional[str] = None
    property_address: Optional[str] = None
    amount: Optional[Decimal] = None
    payment_method: Optional[str] = None
    payment_method_label_en: Optional[str] = None
    payment_method_label_ar: Optional[str] = None
    transaction_number: Optional[str] = None
    is_combined: bool = False
    combined_transaction_count: int = 1


class RentVoucherPrintDataOut(BaseModel):
    """The bilingual print-ready DTO — same contract as
    RentalService.get_receipt_document / FinancialService's invoice
    print DTOs: the frontend renders the actual A4 / 4-per-page /
    RTL+LTR layout and calls the browser print dialog; the backend only
    supplies the data. See docs/rent-voucher-module.md for why."""
    voucher_id: int
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


class GenerateVouchersResultOut(BaseModel):
    vouchers: List[RentVoucherOut]
    created_count: int
    already_existed_count: int
    message: str


class BulkVoucherIdsRequest(BaseModel):
    voucher_ids: List[int]
