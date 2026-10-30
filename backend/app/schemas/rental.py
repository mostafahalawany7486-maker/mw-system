from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from app.schemas.common import AuditFieldsOut

VALID_PAYMENT_FREQUENCIES = {"monthly", "quarterly", "semi_annual", "annual", "one_time", "custom"}
VALID_DEPOSIT_STATUSES = {"held", "returned", "partially_returned", "forfeited"}
VALID_DISCOUNT_TYPES = {"none", "percentage", "fixed"}
VALID_LATE_FEE_TYPES = {"percentage", "fixed"}
VALID_INSTALLMENT_STATUSES = {"pending", "paid", "overdue", "cancelled"}


# ---------------- Payment Installment ----------------
class RentalInstallmentCreate(BaseModel):
    due_date: date
    amount: Decimal
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    notes: Optional[str] = None


class RentalInstallmentUpdate(BaseModel):
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    late_fee_amount: Optional[Decimal] = None
    payment_status: Optional[str] = None
    paid_date: Optional[date] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("payment_status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_INSTALLMENT_STATUSES:
            raise ValueError(f"payment_status must be one of {sorted(VALID_INSTALLMENT_STATUSES)}")
        return v


class RentalInstallmentOut(AuditFieldsOut):
    contract_id: int
    installment_number: int
    due_date: date
    amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    late_fee_amount: Decimal
    total_payable: Decimal
    payment_status: str
    paid_date: Optional[date] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    is_overdue: bool = False
    receipt_number: Optional[str] = None
    printed_at: Optional[datetime] = None
    print_count: int = 0


class GenerateScheduleRequest(BaseModel):
    overwrite_existing: bool = False


# ---------------- Rental Contract ----------------
class RentalContractCreate(BaseModel):
    tenant_id: int
    property_id: int
    branch_id: Optional[int] = None
    start_date: date
    end_date: date
    signed_date: Optional[date] = None
    is_renewable: bool = True
    auto_renew: bool = False
    renewal_notice_days: int = 30
    payment_frequency: str = "monthly"
    rent_amount: Decimal
    currency_id: Optional[int] = None
    security_deposit_amount: Decimal = Decimal("0")

    discount_type: str = "none"
    discount_value: Decimal = Decimal("0")
    discount_reason: Optional[str] = None

    tax_rate: Decimal = Decimal("0")

    late_fee_type: str = "fixed"
    late_fee_value: Decimal = Decimal("0")
    late_fee_grace_period_days: int = 5

    notes_summary: Optional[str] = None

    @field_validator("payment_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in VALID_PAYMENT_FREQUENCIES:
            raise ValueError(f"payment_frequency must be one of {sorted(VALID_PAYMENT_FREQUENCIES)}")
        return v

    @field_validator("discount_type")
    @classmethod
    def validate_discount_type(cls, v: str) -> str:
        if v not in VALID_DISCOUNT_TYPES:
            raise ValueError(f"discount_type must be one of {sorted(VALID_DISCOUNT_TYPES)}")
        return v

    @field_validator("late_fee_type")
    @classmethod
    def validate_late_fee_type(cls, v: str) -> str:
        if v not in VALID_LATE_FEE_TYPES:
            raise ValueError(f"late_fee_type must be one of {sorted(VALID_LATE_FEE_TYPES)}")
        return v

    @field_validator("rent_amount", "security_deposit_amount", "discount_value", "late_fee_value")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

    @field_validator("tax_rate")
    @classmethod
    def validate_tax_rate(cls, v: Decimal) -> Decimal:
        if not (0 <= v <= 100):
            raise ValueError("tax_rate must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def validate_dates_and_discount(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if self.discount_type == "percentage" and not (0 <= self.discount_value <= 100):
            raise ValueError("discount_value must be between 0 and 100 when discount_type is 'percentage'")
        return self


class RentalContractUpdate(BaseModel):
    branch_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    signed_date: Optional[date] = None
    auto_renew: Optional[bool] = None
    is_renewable: Optional[bool] = None
    renewal_notice_days: Optional[int] = None
    payment_frequency: Optional[str] = None
    rent_amount: Optional[Decimal] = None
    currency_id: Optional[int] = None
    security_deposit_amount: Optional[Decimal] = None
    security_deposit_status: Optional[str] = None

    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    discount_reason: Optional[str] = None

    tax_rate: Optional[Decimal] = None

    late_fee_type: Optional[str] = None
    late_fee_value: Optional[Decimal] = None
    late_fee_grace_period_days: Optional[int] = None

    notes_summary: Optional[str] = None

    @field_validator("payment_frequency")
    @classmethod
    def validate_frequency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PAYMENT_FREQUENCIES:
            raise ValueError(f"payment_frequency must be one of {sorted(VALID_PAYMENT_FREQUENCIES)}")
        return v

    @field_validator("security_deposit_status")
    @classmethod
    def validate_deposit_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_DEPOSIT_STATUSES:
            raise ValueError(f"security_deposit_status must be one of {sorted(VALID_DEPOSIT_STATUSES)}")
        return v

    @field_validator("discount_type")
    @classmethod
    def validate_discount_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_DISCOUNT_TYPES:
            raise ValueError(f"discount_type must be one of {sorted(VALID_DISCOUNT_TYPES)}")
        return v

    @field_validator("late_fee_type")
    @classmethod
    def validate_late_fee_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_LATE_FEE_TYPES:
            raise ValueError(f"late_fee_type must be one of {sorted(VALID_LATE_FEE_TYPES)}")
        return v


class TerminateRentalRequest(BaseModel):
    terminated_date: date
    termination_reason: str


class RenewRentalRequest(BaseModel):
    new_end_date: date
    new_start_date: Optional[date] = None
    rent_amount: Optional[Decimal] = None
    notes_summary: Optional[str] = None


class RentalContractListItemOut(AuditFieldsOut):
    contract_number: str
    tenant_id: int
    tenant_display_name: Optional[str] = None
    property_id: int
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    start_date: date
    end_date: date
    contract_status: str
    rent_amount: Decimal
    currency_id: Optional[int] = None
    is_expiring_soon: bool = False
    days_until_expiry: int = 0
    tenant_is_blacklisted: bool = False


class RentalContractDetailOut(AuditFieldsOut):
    contract_number: str
    tenant_id: int
    tenant_display_name: Optional[str] = None
    property_id: int
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    branch_id: Optional[int] = None
    start_date: date
    end_date: date
    signed_date: Optional[date] = None
    auto_renew: bool
    is_renewable: bool
    renewal_notice_days: int
    renewal_reminder_sent: bool
    renewed_from_contract_id: Optional[int] = None
    payment_frequency: str
    rent_amount: Decimal
    currency_id: Optional[int] = None
    security_deposit_amount: Decimal
    security_deposit_status: str

    discount_type: str
    discount_value: Decimal
    discount_reason: Optional[str] = None
    discount_amount_computed: Decimal

    tax_rate: Decimal
    tax_amount_computed: Decimal

    late_fee_type: str
    late_fee_value: Decimal
    late_fee_grace_period_days: int

    contract_status: str
    terminated_date: Optional[date] = None
    termination_reason: Optional[str] = None
    notes_summary: Optional[str] = None
    is_expiring_soon: bool = False
    days_until_expiry: int = 0
    tenant_is_blacklisted: bool = False

    installments: List[RentalInstallmentOut] = []


class RentalDashboardOut(BaseModel):
    total_contracts: int
    active_contracts: int
    draft_contracts: int
    expiring_soon: int
    terminated_contracts: int
    total_outstanding_amount: Decimal
    upcoming_renewals: List[RentalContractListItemOut] = []


# ---------------- Rental Receipt Module ----------------
class GenerateMonthlyReceiptsRequest(BaseModel):
    year: int
    month: int

    @field_validator("month")
    @classmethod
    def validate_month(cls, v: int) -> int:
        if not 1 <= v <= 12:
            raise ValueError("month must be between 1 and 12")
        return v


class RentalReceiptOut(BaseModel):
    """Everything the printable receipt template needs, in one response —
    deliberately excludes internal payment_status, contract_number, and
    tenant phone/civil-ID, per the approved Phase 1 content design."""
    installment_id: int
    receipt_number: str
    receipt_date: date
    rental_month: str  # e.g. "2026-07", formatted for display by the frontend
    tenant_name: str
    tenant_address: Optional[str] = None
    building_name: Optional[str] = None
    building_number: Optional[str] = None
    unit_name: Optional[str] = None
    unit_number: Optional[str] = None
    amount: Decimal
    amount_in_words_en: str
    amount_in_words_ar: str
    payment_method: Optional[str] = None
    bank_name: Optional[str] = None
    reference_number: Optional[str] = None  # also doubles as cheque number when payment_method == "cheque"
    print_count: int
    printed_at: Optional[datetime] = None


class PaymentConfirmationIn(BaseModel):
    account_id: int
    payment_method: str
    reference_number: Optional[str] = None
    transaction_date: date
    notes: Optional[str] = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        valid = {"cash", "bank_transfer", "cheque", "card", "online", "knet"}
        if v not in valid:
            raise ValueError(f"payment_method must be one of {sorted(valid)}")
        return v


class RentalReceiptSearchItemOut(BaseModel):
    installment_id: int
    receipt_number: str
    tenant_display_name: Optional[str] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    due_date: date
    amount: Decimal
    payment_status: str
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    print_count: int
