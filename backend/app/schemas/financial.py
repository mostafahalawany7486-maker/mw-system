from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from app.schemas.common import AuditFieldsOut

VALID_ACCOUNT_TYPES = {"cash", "bank"}
VALID_TRANSACTION_TYPES = {
    "tenant_payment", "owner_payment", "expense", "income",
    "deposit_received", "deposit_refund", "refund",
}
VALID_PAYMENT_METHODS = {"cash", "bank_transfer", "cheque", "card", "online", "knet"}
VALID_INVOICE_STATUSES = {"draft", "sent", "paid", "partially_paid", "overdue", "cancelled", "void"}

OUTFLOW_TYPES = {"owner_payment", "expense", "deposit_refund", "refund"}


# ---------------- Financial Account ----------------
class FinancialAccountCreate(BaseModel):
    account_type: str
    name: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    iban: Optional[str] = None
    currency_id: Optional[int] = None
    branch_id: Optional[int] = None
    opening_balance: Decimal = Decimal("0")
    is_default: bool = False

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        if v not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {sorted(VALID_ACCOUNT_TYPES)}")
        return v

    @model_validator(mode="after")
    def validate_bank_fields(self):
        if self.account_type == "bank" and not self.bank_name:
            raise ValueError("bank_name is required for bank accounts")
        return self


class FinancialAccountUpdate(BaseModel):
    name: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    iban: Optional[str] = None
    currency_id: Optional[int] = None
    branch_id: Optional[int] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None
    gl_account_id: Optional[int] = None  # Phase 10: links this account to its Chart of Accounts GL ledger account


class FinancialAccountOut(AuditFieldsOut):
    account_code: str
    account_type: str
    name: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    iban: Optional[str] = None
    currency_id: Optional[int] = None
    branch_id: Optional[int] = None
    opening_balance: Decimal
    is_default: bool
    current_balance: Decimal = Decimal("0")
    gl_account_id: Optional[int] = None


# ---------------- Transaction ----------------
class TransactionCreate(BaseModel):
    transaction_type: str
    amount: Decimal
    account_id: int
    tenant_id: Optional[int] = None
    owner_id: Optional[int] = None
    property_id: Optional[int] = None
    rental_contract_id: Optional[int] = None
    rental_installment_id: Optional[int] = None
    lease_agreement_id: Optional[int] = None
    lease_installment_id: Optional[int] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_date: date
    description: Optional[str] = None

    @field_validator("transaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TRANSACTION_TYPES:
            raise ValueError(f"transaction_type must be one of {sorted(VALID_TRANSACTION_TYPES)} (transfers use the dedicated /financial/transfers endpoint)")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of {sorted(VALID_PAYMENT_METHODS)}")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def validate_counterparty(self):
        if self.transaction_type in ("tenant_payment", "deposit_received", "deposit_refund", "refund") and not self.tenant_id:
            raise ValueError(f"tenant_id is required for transaction_type={self.transaction_type}")
        if self.transaction_type == "owner_payment" and not self.owner_id:
            raise ValueError("owner_id is required for transaction_type=owner_payment")
        return self


class TransactionUpdate(BaseModel):
    transaction_status: Optional[str] = None
    category: Optional[str] = None
    reference_number: Optional[str] = None
    description: Optional[str] = None

    @field_validator("transaction_status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"completed", "cancelled"}:
            raise ValueError("transaction_status must be 'completed' or 'cancelled'")
        return v


class TransactionOut(AuditFieldsOut):
    transaction_number: str
    transaction_type: str
    direction: str
    transaction_status: str
    amount: Decimal
    account_id: int
    account_name: Optional[str] = None
    transfer_pair_id: Optional[int] = None
    tenant_id: Optional[int] = None
    tenant_display_name: Optional[str] = None
    owner_id: Optional[int] = None
    owner_display_name: Optional[str] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    rental_contract_id: Optional[int] = None
    rental_installment_id: Optional[int] = None
    lease_agreement_id: Optional[int] = None
    lease_installment_id: Optional[int] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_date: date
    description: Optional[str] = None
    receipt_number: Optional[str] = None
    receipt_id: Optional[int] = None


class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Decimal
    transaction_date: date
    reference_number: Optional[str] = None
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def validate_distinct_accounts(self):
        if self.from_account_id == self.to_account_id:
            raise ValueError("from_account_id and to_account_id must be different")
        return self


# ---------------- Receipt ----------------
class ReceiptOut(AuditFieldsOut):
    receipt_number: str
    transaction_id: int
    issued_date: date
    notes: Optional[str] = None
    transaction: Optional[TransactionOut] = None
    invoice_id: Optional[int] = None
    printed_at: Optional[datetime] = None
    print_count: int = 0


# ---------------- Invoice ----------------
class InvoiceCreate(BaseModel):
    tenant_id: int
    rental_contract_id: Optional[int] = None
    property_id: Optional[int] = None
    amount: Decimal
    issue_date: date
    due_date: date
    description: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.issue_date:
            raise ValueError("due_date cannot be before issue_date")
        return self


class InvoiceUpdate(BaseModel):
    amount: Optional[Decimal] = None
    due_date: Optional[date] = None
    invoice_status: Optional[str] = None
    description: Optional[str] = None
    property_id: Optional[int] = None

    @field_validator("invoice_status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_INVOICE_STATUSES:
            raise ValueError(f"invoice_status must be one of {sorted(VALID_INVOICE_STATUSES)}")
        return v


class RecordInvoicePaymentRequest(BaseModel):
    account_id: int
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None
    transaction_date: date
    amount: Optional[Decimal] = None  # partial payment support; defaults to full outstanding balance

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class VoidCancelInvoiceRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason is required")
        return v


class InvoiceOut(AuditFieldsOut):
    invoice_number: str
    tenant_id: int
    tenant_display_name: Optional[str] = None
    rental_contract_id: Optional[int] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    unit_number: Optional[str] = None
    amount: Decimal
    issue_date: date
    due_date: date
    invoice_status: str
    description: Optional[str] = None
    paid_transaction_id: Optional[int] = None
    is_overdue: bool = False
    billing_cycle: Optional[str] = None
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    amount_paid: Decimal = Decimal("0")
    outstanding_amount: Decimal = Decimal("0")
    void_reason: Optional[str] = None
    voided_at: Optional[datetime] = None
    printed_at: Optional[datetime] = None
    print_count: int = 0
    delivered_at: Optional[datetime] = None
    qr_token: Optional[str] = None


# ---------------- Outstanding Balance ----------------
class OutstandingBalanceItem(BaseModel):
    id: int
    display_name: str
    outstanding_amount: Decimal
    overdue_count: int
    pending_count: int


class OutstandingBalanceOut(BaseModel):
    tenants: List[OutstandingBalanceItem] = []
    owners: List[OutstandingBalanceItem] = []
    total_tenant_outstanding: Decimal = Decimal("0")
    total_owner_outstanding: Decimal = Decimal("0")


class FinancialDashboardOut(BaseModel):
    total_cash_balance: Decimal
    total_bank_balance: Decimal
    total_income_this_month: Decimal
    total_expense_this_month: Decimal
    total_tenant_outstanding: Decimal
    total_owner_outstanding: Decimal
    accounts: List[FinancialAccountOut] = []
    invoices_generated_this_month: int = 0
    invoices_paid_this_month: int = 0
    invoices_due_today: int = 0
    total_overdue_invoice_amount: Decimal = Decimal("0")
    collection_rate_percentage: float = 0.0
    top_debtors: List[dict] = []


# ---------------- Rent Billing Engine ----------------
VALID_BILLING_CYCLES = {"monthly", "quarterly", "semi_annual", "annual", "one_time", "custom"}


class GenerateBulkInvoicesRequest(BaseModel):
    billing_period_start: date
    property_ids: Optional[List[int]] = None  # None = every active contract; scope to a building/property/owner's unit ids otherwise


class ApproveInvoicesRequest(BaseModel):
    invoice_ids: List[int]


class BulkPrintRequest(BaseModel):
    invoice_ids: List[int]


class InvoicePrintOut(BaseModel):
    """The printable document DTO — built from the frozen `snapshot`,
    never from live tenant/property data, so the document is byte-for-
    byte identical to what was generated even if the underlying records
    change later. Deliberately excludes invoice_status, internal notes,
    and audit info (see the tenant-copy content rules)."""
    invoice_id: int
    invoice_number: str
    issue_date: date
    due_date: date
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    tenant_name: Optional[str] = None
    tenant_address: Optional[str] = None
    tenant_civil_id: Optional[str] = None
    tenant_phone: Optional[str] = None
    property_title: Optional[str] = None
    property_code: Optional[str] = None
    unit_number: Optional[str] = None
    building_name: Optional[str] = None
    building_number: Optional[str] = None
    contract_number: Optional[str] = None
    rent_amount: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[str] = None
    tax_rate: Optional[str] = None
    amount: Decimal
    amount_paid: Decimal
    outstanding_amount: Decimal
    company_name: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    company_website: Optional[str] = None
    qr_verification_url: Optional[str] = None
    qr_code_data_uri: Optional[str] = None
    print_count: int = 0


class InvoiceVerificationOut(BaseModel):
    """Deliberately minimal — what the QR code's public verification URL
    returns. No amounts, no tenant details, nothing sensitive; just
    enough to confirm "yes, this is a real invoice we issued"."""
    invoice_number: str
    issue_date: date
    invoice_status: str
    is_valid: bool
