from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.schemas.common import AuditFieldsOut

VALID_MANUAL_ENTRY_TYPES = {"adjustment", "opening_balance", "rental_income", "management_fee"}
VALID_EXPENSE_CATEGORIES = {
    "maintenance", "municipality_fees", "government_fees", "electricity", "water",
    "emergency_repairs", "insurance", "other",
}


class OwnerLedgerEntryCreate(BaseModel):
    """Manual entry — POST /owner-ledger. For Rental Income, Management
    Fee, Opening Balance, and general Adjustments. Recoverable Expense
    and Recovered Amount each have their own dedicated endpoint (see
    RecoverableExpenseCreate / RecoveredPaymentCreate below) since they
    carry extra required context (an account to actually move money
    through) that a generic manual entry doesn't."""
    owner_id: int
    property_id: Optional[int] = None
    transaction_date: date
    transaction_type: str
    description: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

    @field_validator("transaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_MANUAL_ENTRY_TYPES:
            raise ValueError(f"transaction_type must be one of {sorted(VALID_MANUAL_ENTRY_TYPES)} for a manual entry")
        return v

    @field_validator("debit", "credit")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("debit/credit cannot be negative")
        return v


class RecoverableExpenseCreate(BaseModel):
    owner_id: int
    property_id: Optional[int] = None
    account_id: int
    amount: Decimal
    expense_category: str
    description: str
    payment_date: date
    reference_number: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v

    @field_validator("expense_category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in VALID_EXPENSE_CATEGORIES:
            raise ValueError(f"expense_category must be one of {sorted(VALID_EXPENSE_CATEGORIES)}")
        return v


class RecoveredPaymentCreate(BaseModel):
    owner_id: int
    property_id: Optional[int] = None
    account_id: int
    amount: Decimal
    payment_method: str
    payment_date: date
    reference_number: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v


class PayOwnerRequest(BaseModel):
    """Pays down this owner's current Owner Ledger balance directly —
    not tied to any one Lease installment. See
    OwnerLedgerSettlementService.pay_owner_balance()."""
    account_id: int
    amount: Decimal
    payment_method: Optional[str] = None
    transaction_date: date
    reference_number: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v


class ReverseEntryRequest(BaseModel):
    reason: str
    reversal_date: Optional[date] = None


class OwnerLedgerEntryOut(AuditFieldsOut):
    owner_id: int
    owner_name: Optional[str] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    transaction_date: date
    transaction_type: str
    expense_category: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    entry_status: str
    reversal_of_id: Optional[int] = None
    reversed_by_id: Optional[int] = None


class OwnerBalanceOut(BaseModel):
    owner_id: int
    current_balance: Decimal
    outstanding_recoverable_expenses: Decimal


class OwnerDashboardOut(BaseModel):
    owner_id: int
    current_balance: Decimal
    outstanding_recoverable_expenses: Decimal
    monthly_income: Decimal
    monthly_expenses: Decimal
    payments_made: Decimal
    payments_received: Decimal


class OwnerStatementLineOut(BaseModel):
    label: str
    debit: Decimal
    credit: Decimal
    net: Decimal


class OwnerStatementOut(BaseModel):
    owner_id: int
    owner_name: Optional[str] = None
    date_from: date
    date_to: date
    opening_balance: Decimal
    rental_income: Decimal
    management_fees: Decimal
    recoverable_expenses: Decimal
    recovered_amounts: Decimal
    owner_payments: Decimal
    other_adjustments: Decimal
    net_movement: Decimal
    closing_balance: Decimal
    line_items: List[OwnerLedgerEntryOut] = []
