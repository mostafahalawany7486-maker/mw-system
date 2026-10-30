from datetime import date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator, model_validator
from app.schemas.common import AuditFieldsOut

VALID_ACCOUNT_TYPES = {"asset", "liability", "equity", "revenue", "expense"}
VALID_ENTRY_STATUSES = {"draft", "posted", "reversed"}
VALID_TRANSACTION_TYPES_FOR_RULES = {
    "tenant_payment", "owner_payment", "expense", "income",
    "deposit_received", "deposit_refund", "refund",
}


# ---------------- Chart of Accounts ----------------
class ChartOfAccountCreate(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    account_subtype: Optional[str] = None
    parent_account_id: Optional[int] = None
    allow_posting: bool = True
    description: Optional[str] = None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        if v not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {sorted(VALID_ACCOUNT_TYPES)}")
        return v


class ChartOfAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    account_subtype: Optional[str] = None
    parent_account_id: Optional[int] = None
    allow_posting: Optional[bool] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ChartOfAccountOut(AuditFieldsOut):
    account_code: str
    account_name: str
    account_type: str
    account_subtype: Optional[str] = None
    parent_account_id: Optional[int] = None
    parent_account_name: Optional[str] = None
    allow_posting: bool
    description: Optional[str] = None
    normal_balance: str = "debit"
    balance: Optional[Decimal] = None


# ---------------- Cost Centers ----------------
class CostCenterCreate(BaseModel):
    cost_center_code: str
    name: str
    property_id: Optional[int] = None
    branch_id: Optional[int] = None
    description: Optional[str] = None


class CostCenterUpdate(BaseModel):
    name: Optional[str] = None
    property_id: Optional[int] = None
    branch_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None


class CostCenterOut(AuditFieldsOut):
    cost_center_code: str
    name: str
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    branch_id: Optional[int] = None
    description: Optional[str] = None


# ---------------- VAT Rates ----------------
class VatRateCreate(BaseModel):
    code: str
    name: str
    rate_percentage: Decimal
    gl_account_id: Optional[int] = None
    is_default: bool = False

    @field_validator("rate_percentage")
    @classmethod
    def validate_rate(cls, v: Decimal) -> Decimal:
        if not (0 <= v <= 100):
            raise ValueError("rate_percentage must be between 0 and 100")
        return v


class VatRateUpdate(BaseModel):
    name: Optional[str] = None
    rate_percentage: Optional[Decimal] = None
    gl_account_id: Optional[int] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class VatRateOut(AuditFieldsOut):
    code: str
    name: str
    rate_percentage: Decimal
    gl_account_id: Optional[int] = None
    gl_account_name: Optional[str] = None
    is_default: bool


# ---------------- Posting Rules ----------------
class PostingRuleCreate(BaseModel):
    transaction_type: str
    category: Optional[str] = None
    offset_account_id: int
    vat_rate_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    description: Optional[str] = None

    @field_validator("transaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_TRANSACTION_TYPES_FOR_RULES:
            raise ValueError(f"transaction_type must be one of {sorted(VALID_TRANSACTION_TYPES_FOR_RULES)}")
        return v


class PostingRuleUpdate(BaseModel):
    offset_account_id: Optional[int] = None
    vat_rate_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    description: Optional[str] = None


class PostingRuleOut(AuditFieldsOut):
    transaction_type: str
    category: Optional[str] = None
    offset_account_id: int
    offset_account_name: Optional[str] = None
    vat_rate_id: Optional[int] = None
    cost_center_id: Optional[int] = None
    description: Optional[str] = None


# ---------------- Journal Entries ----------------
class JournalEntryLineCreate(BaseModel):
    account_id: int
    cost_center_id: Optional[int] = None
    property_id: Optional[int] = None
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    description: Optional[str] = None
    vat_rate_id: Optional[int] = None
    vat_amount: Decimal = Decimal("0")

    @field_validator("debit_amount", "credit_amount", "vat_amount")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_one_sided(self):
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValueError("A line cannot have both a debit and a credit amount")
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValueError("A line must have either a debit or a credit amount greater than 0")
        return self


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: Optional[str] = None
    reference_number: Optional[str] = None
    lines: List[JournalEntryLineCreate]

    @field_validator("lines")
    @classmethod
    def validate_min_lines(cls, v: List[JournalEntryLineCreate]) -> List[JournalEntryLineCreate]:
        if len(v) < 2:
            raise ValueError("A journal entry needs at least 2 lines")
        return v

    @model_validator(mode="after")
    def validate_balanced(self):
        total_debit = sum((l.debit_amount for l in self.lines), Decimal("0"))
        total_credit = sum((l.credit_amount for l in self.lines), Decimal("0"))
        if total_debit != total_credit:
            raise ValueError(f"Entry is not balanced: total debits ({total_debit}) must equal total credits ({total_credit})")
        return self


class JournalEntryUpdate(BaseModel):
    description: Optional[str] = None
    reference_number: Optional[str] = None


class JournalEntryLineOut(AuditFieldsOut):
    journal_entry_id: int
    account_id: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    cost_center_id: Optional[int] = None
    property_id: Optional[int] = None
    property_title: Optional[str] = None
    debit_amount: Decimal
    credit_amount: Decimal
    description: Optional[str] = None
    vat_rate_id: Optional[int] = None
    vat_amount: Decimal


class JournalEntryListItemOut(AuditFieldsOut):
    entry_number: str
    entry_date: date
    description: Optional[str] = None
    reference_number: Optional[str] = None
    source_type: str
    source_transaction_id: Optional[int] = None
    entry_status: str
    posted_at: Optional[str] = None
    total_debit: Decimal = Decimal("0")
    total_credit: Decimal = Decimal("0")


class JournalEntryDetailOut(JournalEntryListItemOut):
    reversed_entry_id: Optional[int] = None
    lines: List[JournalEntryLineOut] = []


# ---------------- Reports ----------------
class TrialBalanceLineOut(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: str
    debit_balance: Decimal
    credit_balance: Decimal


class TrialBalanceOut(BaseModel):
    as_of_date: date
    lines: List[TrialBalanceLineOut]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool


class GeneralLedgerLineOut(BaseModel):
    journal_entry_id: int
    entry_number: str
    entry_date: date
    description: Optional[str] = None
    debit_amount: Decimal
    credit_amount: Decimal
    running_balance: Decimal


class GeneralLedgerOut(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    opening_balance: Decimal
    lines: List[GeneralLedgerLineOut]
    closing_balance: Decimal


class BalanceSheetSectionOut(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    balance: Decimal


class BalanceSheetOut(BaseModel):
    as_of_date: date
    assets: List[BalanceSheetSectionOut]
    liabilities: List[BalanceSheetSectionOut]
    equity: List[BalanceSheetSectionOut]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool


class IncomeStatementOut(BaseModel):
    date_from: date
    date_to: date
    revenue: List[BalanceSheetSectionOut]
    expenses: List[BalanceSheetSectionOut]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class CashFlowLineOut(BaseModel):
    transaction_type: str
    total_amount: Decimal


class CashFlowOut(BaseModel):
    date_from: date
    date_to: date
    operating_activities: List[CashFlowLineOut]
    net_operating_cash_flow: Decimal
    net_change_in_cash: Decimal
    opening_cash_balance: Decimal
    closing_cash_balance: Decimal


class VatReportLineOut(BaseModel):
    vat_rate_id: int
    vat_code: str
    vat_name: str
    rate_percentage: Decimal
    output_vat: Decimal
    input_vat: Decimal
    net_vat: Decimal


class VatReportOut(BaseModel):
    date_from: date
    date_to: date
    lines: List[VatReportLineOut]
    total_output_vat: Decimal
    total_input_vat: Decimal
    total_net_vat: Decimal


# ---------------- Property Profit Center reports ----------------
class PropertyCashFlowActivityOut(BaseModel):
    transaction_type: str
    total_amount: Decimal


class PropertyCashFlowOut(BaseModel):
    """Unlike the portfolio CashFlowOut, there is no opening/closing bank
    balance here — cash isn't physically segregated per property in this
    system, so this reports the property's own net cash contribution
    instead (see AccountingReportService.property_cash_flow)."""
    property_id: int
    date_from: date
    date_to: date
    activities: List[PropertyCashFlowActivityOut]
    net_cash_flow: Decimal


class PropertyLedgerLineOut(BaseModel):
    journal_entry_id: int
    entry_number: str
    entry_date: date
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    description: Optional[str] = None
    debit_amount: Decimal
    credit_amount: Decimal


class PropertyLedgerOut(BaseModel):
    property_id: int
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    lines: List[PropertyLedgerLineOut]
    total_debit: Decimal
    total_credit: Decimal


class PropertyBalanceSummaryOut(BaseModel):
    property_id: int
    as_of_date: date
    lines: List[TrialBalanceLineOut]
    total_debit: Decimal
    total_credit: Decimal
