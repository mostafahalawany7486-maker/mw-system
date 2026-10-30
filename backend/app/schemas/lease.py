from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from app.schemas.common import AuditFieldsOut

VALID_PAYMENT_FREQUENCIES = {"monthly", "quarterly", "semi_annual", "annual", "one_time", "custom"}
VALID_DEPOSIT_STATUSES = {"held", "returned", "partially_returned", "forfeited"}


# ---------------- Payment Installment ----------------
class LeasePaymentInstallmentCreate(BaseModel):
    due_date: date
    amount: Decimal
    notes: Optional[str] = None


class LeasePaymentInstallmentUpdate(BaseModel):
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    payment_status: Optional[str] = None
    paid_date: Optional[date] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("payment_status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"pending", "paid", "overdue", "cancelled"}:
            raise ValueError("Invalid installment status")
        return v


class LeasePaymentInstallmentOut(AuditFieldsOut):
    lease_id: int
    installment_number: int
    due_date: date
    amount: Decimal
    payment_status: str
    paid_date: Optional[date] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    is_overdue: bool = False


class GenerateScheduleRequest(BaseModel):
    """Auto-generate installments for a lease based on its payment_frequency."""
    overwrite_existing: bool = False


# ---------------- Lease Agreement ----------------
class LeaseAgreementCreate(BaseModel):
    owner_id: int
    property_id: Optional[int] = None
    branch_id: Optional[int] = None
    property_reference: str
    start_date: date
    end_date: date
    signed_date: Optional[date] = None
    is_renewable: bool = True
    renewal_notice_days: int = 30
    payment_frequency: str = "monthly"
    rent_amount: Decimal
    currency_id: Optional[int] = None
    security_deposit_amount: Decimal = Decimal("0")
    notes_summary: Optional[str] = None

    @field_validator("payment_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        if v not in VALID_PAYMENT_FREQUENCIES:
            raise ValueError(f"payment_frequency must be one of {sorted(VALID_PAYMENT_FREQUENCIES)}")
        return v

    @field_validator("rent_amount", "security_deposit_amount")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class LeaseAgreementUpdate(BaseModel):
    branch_id: Optional[int] = None
    property_id: Optional[int] = None
    property_reference: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    signed_date: Optional[date] = None
    is_renewable: Optional[bool] = None
    renewal_notice_days: Optional[int] = None
    payment_frequency: Optional[str] = None
    rent_amount: Optional[Decimal] = None
    currency_id: Optional[int] = None
    security_deposit_amount: Optional[Decimal] = None
    security_deposit_status: Optional[str] = None
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


class TerminateLeaseRequest(BaseModel):
    terminated_date: date
    termination_reason: str


class RenewLeaseRequest(BaseModel):
    new_end_date: date
    new_start_date: Optional[date] = None  # defaults to old end_date + 1 day if omitted
    rent_amount: Optional[Decimal] = None  # allows adjusting rent on renewal
    notes_summary: Optional[str] = None


class LeaseAgreementListItemOut(AuditFieldsOut):
    contract_number: str
    owner_id: int
    owner_display_name: Optional[str] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    property_reference: str
    start_date: date
    end_date: date
    contract_status: str
    rent_amount: Decimal
    currency_id: Optional[int] = None
    is_expiring_soon: bool = False
    days_until_expiry: int = 0


class LeaseAgreementDetailOut(AuditFieldsOut):
    contract_number: str
    owner_id: int
    owner_display_name: Optional[str] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    branch_id: Optional[int] = None
    property_reference: str
    start_date: date
    end_date: date
    signed_date: Optional[date] = None
    is_renewable: bool
    renewal_notice_days: int
    renewal_reminder_sent: bool
    renewed_from_lease_id: Optional[int] = None
    payment_frequency: str
    rent_amount: Decimal
    currency_id: Optional[int] = None
    security_deposit_amount: Decimal
    security_deposit_status: str
    contract_status: str
    terminated_date: Optional[date] = None
    termination_reason: Optional[str] = None
    notes_summary: Optional[str] = None
    is_expiring_soon: bool = False
    days_until_expiry: int = 0
    installments: List[LeasePaymentInstallmentOut] = []


class LeaseDashboardOut(BaseModel):
    total_leases: int
    active_leases: int
    draft_leases: int
    expiring_soon: int
    terminated_leases: int
    total_outstanding_amount: Decimal
    upcoming_renewals: List[LeaseAgreementListItemOut] = []


class SettleOwnerInstallmentRequest(BaseModel):
    """Pays out one owner lease installment for real (creates the actual
    Transaction, generates a receipt) AND records the matching entry in
    the Owner Ledger in the same call — see
    app/business_workflows/owner_ledger/owner_settlement_service.py."""
    account_id: int
    transaction_date: date
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
