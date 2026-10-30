from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from app.schemas.common import AuditFieldsOut

VALID_PAYMENT_METHODS = {"cash", "knet", "bank_transfer", "cheque", "online", "mixed"}


class PaymentAllocationIn(BaseModel):
    invoice_id: int
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Allocation amount must be greater than zero")
        return v


class PaymentCreate(BaseModel):
    tenant_id: int
    account_id: int
    payment_method: str
    payment_date: date
    amount: Decimal
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    rental_contract_id: Optional[int] = None
    property_id: Optional[int] = None
    allocations: List[PaymentAllocationIn]

    @field_validator("payment_method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        if v not in VALID_PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of {sorted(VALID_PAYMENT_METHODS)}")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v

    @field_validator("allocations")
    @classmethod
    def validate_allocations_non_empty(cls, v: List[PaymentAllocationIn]) -> List[PaymentAllocationIn]:
        if not v:
            raise ValueError("At least one allocation is required")
        return v

    @model_validator(mode="after")
    def validate_amount_matches_allocations(self):
        total = sum((a.amount for a in self.allocations), Decimal("0"))
        if total != self.amount:
            raise ValueError(f"amount ({self.amount}) must equal the sum of allocation amounts ({total})")
        return self


class VerifyPaymentRequest(BaseModel):
    notes: Optional[str] = None


class RefundPaymentRequest(BaseModel):
    reason: str
    amount: Optional[Decimal] = None  # defaults to the full payment amount


class ReversePaymentRequest(BaseModel):
    reason: str


class CancelPaymentRequest(BaseModel):
    reason: str


class PaymentAllocationOut(AuditFieldsOut):
    payment_id: int
    invoice_id: int
    invoice_number: Optional[str] = None
    amount: Decimal
    transaction_id: Optional[int] = None


class PaymentOut(AuditFieldsOut):
    payment_number: str
    tenant_id: int
    tenant_name: Optional[str] = None
    rental_contract_id: Optional[int] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    building_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    account_id: int
    payment_method: str
    payment_date: date
    amount: Decimal
    currency: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_status: str
    cancellation_reason: Optional[str] = None
    refund_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    reversed_at: Optional[datetime] = None
    allocations: List[PaymentAllocationOut] = []


class CollectionDashboardOut(BaseModel):
    collected_today: Decimal
    collected_this_month: Decimal
    total_outstanding: Decimal
    overdue_amount: Decimal
    collection_percentage: Decimal
    payments_by_status: dict
