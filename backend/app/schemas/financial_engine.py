from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator
from app.models.financial_engine import DepositContractType
from app.schemas.financial import TransactionOut

VALID_CONTRACT_TYPES = set(DepositContractType.ALL)


# ---------------- Ledger views ----------------
class AccountBalanceOut(BaseModel):
    account_id: int
    account_name: str
    account_type: str
    balance: Decimal


class CompanyLedgerOut(BaseModel):
    cash_total: Decimal
    bank_total: Decimal
    total_balance: Decimal
    accounts: List[AccountBalanceOut]


class OwnerLedgerSummaryOut(BaseModel):
    owner_id: int
    current_balance: Decimal
    outstanding_recoverable_expenses: Decimal


class TenantLedgerOut(BaseModel):
    tenant_id: int
    total_paid: Decimal
    total_refunded: Decimal
    total_deposited: Decimal
    total_deposit_refunded: Decimal
    outstanding_rent: Decimal


class PropertyScopedLedgerOut(BaseModel):
    rental_income: Decimal
    operating_expenses: Decimal
    owner_expenses: Decimal
    net_income: Decimal
    building_id: Optional[int] = None
    property_id: Optional[int] = None
    unit_id: Optional[int] = None


class AllLedgersSummaryOut(BaseModel):
    company: CompanyLedgerOut


# ---------------- Deposit lifecycle ----------------
class DepositCreateRequest(BaseModel):
    contract_type: str
    contract_id: int
    account_id: int
    amount: Decimal
    payment_date: date
    reference_number: Optional[str] = None

    @field_validator("contract_type")
    @classmethod
    def validate_contract_type(cls, v: str) -> str:
        if v not in VALID_CONTRACT_TYPES:
            raise ValueError(f"contract_type must be one of {sorted(VALID_CONTRACT_TYPES)}")
        return v

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v


class DepositActionRequest(BaseModel):
    """Shared body for partial/full refund, deduction, forfeit, and
    transfer-to-owner — which fields are required depends on the
    action, enforced in the router/service rather than with five
    near-identical schemas."""
    amount: Optional[Decimal] = None
    account_id: Optional[int] = None
    payment_date: Optional[date] = None
    reason: Optional[str] = None
    reference_number: Optional[str] = None
    owner_id: Optional[int] = None


class DepositLedgerEntryOut(BaseModel):
    id: int
    contract_type: str
    contract_id: int
    action: str
    amount: Decimal
    balance_after: Decimal
    reason: Optional[str] = None
    transaction_id: Optional[int] = None
    reference_number: Optional[str] = None
    action_date: datetime


class DepositSummaryOut(BaseModel):
    contract_type: str
    contract_id: int
    original_amount: Decimal
    remaining_balance: Decimal
    status: str
    entries: List[DepositLedgerEntryOut]


class DepositActionResultOut(BaseModel):
    transaction: Optional[TransactionOut] = None
    ledger_entry: Optional[DepositLedgerEntryOut] = None
    owner_ledger_entry: Optional[dict] = None
    deposit_ledger_entry: Optional[DepositLedgerEntryOut] = None


# ---------------- Refunds ----------------
class RefundRequest(BaseModel):
    refund_type: str  # "payment" | "deposit"
    # payment refund
    payment_id: Optional[int] = None
    # deposit refund
    contract_type: Optional[str] = None
    contract_id: Optional[int] = None
    account_id: Optional[int] = None
    payment_date: Optional[date] = None
    reference_number: Optional[str] = None
    # shared
    amount: Optional[Decimal] = None
    reason: str

    @field_validator("refund_type")
    @classmethod
    def validate_refund_type(cls, v: str) -> str:
        if v not in {"payment", "deposit"}:
            raise ValueError("refund_type must be 'payment' or 'deposit'")
        return v


# ---------------- Adjustments ----------------
class AdjustmentRequest(BaseModel):
    scope: str  # "owner" | "tenant"
    entity_id: int
    amount: Decimal
    description: str
    is_credit: bool = True
    account_id: Optional[int] = None  # required for scope="tenant"
    property_id: Optional[int] = None

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        if v not in {"owner", "tenant"}:
            raise ValueError("scope must be 'owner' or 'tenant'")
        return v

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v


# ---------------- Transfer ----------------
class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal
    transaction_date: date
    description: Optional[str] = None
    reference_number: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v


class TransferResultOut(BaseModel):
    out_transaction: TransactionOut
    in_transaction: TransactionOut


# ---------------- Dashboard ----------------
class FinancialEngineDashboardOut(BaseModel):
    company_cash: Decimal
    owner_outstanding: Decimal
    tenant_outstanding: Decimal
    security_deposits_held: Decimal
    recoverable_expenses_outstanding: Decimal
    recovered_amounts_total: Decimal
    todays_collections: Decimal
    monthly_collections: Decimal
