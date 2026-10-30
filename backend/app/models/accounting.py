"""
Accounting module (Phase 10) — a proper double-entry general ledger sitting
underneath the operational Financial Management module (Phase 8).

Design overview:
- Chart of Accounts is a self-referential tree (header accounts for
  grouping, leaf accounts with allow_posting=True for actual entries).
- Journal Entry + Journal Entry Line is the classic header/lines
  double-entry pattern: every entry must have total debits == total
  credits before it can be posted.
- Automatic Posting works via a PostingRule table that maps a Phase 8
  Transaction (by transaction_type, optionally narrowed by category) to
  an "offset" GL account (revenue/expense/liability). The cash/bank side
  of the entry comes from a new nullable FinancialAccount.gl_account_id
  link (added additively in this phase's migration) — so posting an
  entry never requires guessing which GL cash account to hit. Cost
  Centers let every line optionally be tagged to a property/branch for
  segmented reporting. VAT is handled as a single "VAT Control" account
  per rate (netting payable/receivable) rather than separate output/input
  accounts — a deliberate, documented simplification appropriate for a
  small-to-mid property management operation.
- General Ledger, Trial Balance, Balance Sheet, Income Statement, and
  Cash Flow are NOT stored tables — they're computed live from posted
  Journal Entry Lines, so they can never drift from the underlying
  ledger.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Date, DateTime, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class AccountType:
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"

    DEBIT_NORMAL = {ASSET, EXPENSE}
    CREDIT_NORMAL = {LIABILITY, EQUITY, REVENUE}


class EntryStatus:
    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"


class SourceType:
    MANUAL = "manual"
    SYSTEM = "system"


class ChartOfAccount(BaseModel):
    __tablename__ = "chart_of_accounts"

    account_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    account_subtype: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parent_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True, index=True)
    allow_posting: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parent: Mapped[Optional["ChartOfAccount"]] = relationship(remote_side="ChartOfAccount.id", foreign_keys=[parent_account_id], back_populates="children")
    children: Mapped[list["ChartOfAccount"]] = relationship(back_populates="parent")

    @property
    def normal_balance(self) -> str:
        return "debit" if self.account_type in AccountType.DEBIT_NORMAL else "credit"


class CostCenter(BaseModel):
    __tablename__ = "cost_centers"

    cost_center_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821
    branch: Mapped[Optional["Branch"]] = relationship(foreign_keys=[branch_id])  # noqa: F821

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None


class VatRate(BaseModel):
    """A single 'VAT Control' account per rate, netting payable/receivable
    — a deliberate simplification suited to a small property management
    operation rather than tracking separate output/input VAT accounts."""
    __tablename__ = "vat_rates"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gl_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    gl_account: Mapped[Optional["ChartOfAccount"]] = relationship(foreign_keys=[gl_account_id])


class PostingRule(BaseModel):
    """Maps a Phase 8 Transaction (by type, optionally narrowed by
    category) to the GL account on the non-cash side of the automatic
    journal entry. The cash/bank side is resolved dynamically from the
    FinancialAccount.gl_account_id on the transaction's own account."""
    __tablename__ = "posting_rules"

    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offset_account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False)
    vat_rate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vat_rates.id"), nullable=True)
    cost_center_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    offset_account: Mapped["ChartOfAccount"] = relationship(foreign_keys=[offset_account_id])
    vat_rate: Mapped[Optional["VatRate"]] = relationship(foreign_keys=[vat_rate_id])
    cost_center: Mapped[Optional["CostCenter"]] = relationship(foreign_keys=[cost_center_id])


class JournalEntry(BaseModel):
    __tablename__ = "journal_entries"

    entry_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_type: Mapped[str] = mapped_column(String(10), default=SourceType.MANUAL, index=True)
    source_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    entry_status: Mapped[str] = mapped_column(String(10), default=EntryStatus.DRAFT, index=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)

    lines: Mapped[list["JournalEntryLine"]] = relationship(back_populates="journal_entry", cascade="all, delete-orphan")
    source_transaction: Mapped[Optional["Transaction"]] = relationship(foreign_keys=[source_transaction_id])  # noqa: F821
    reversed_entry: Mapped[Optional["JournalEntry"]] = relationship(remote_side="JournalEntry.id", foreign_keys=[reversed_entry_id])

    @property
    def total_debit(self) -> Decimal:
        return sum((l.debit_amount for l in self.lines), Decimal("0"))

    @property
    def total_credit(self) -> Decimal:
        return sum((l.credit_amount for l in self.lines), Decimal("0"))

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit and self.total_debit > 0


class JournalEntryLine(BaseModel):
    __tablename__ = "journal_entry_lines"

    journal_entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=False, index=True)
    cost_center_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cost_centers.id"), nullable=True, index=True)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)  # Profit Center extension: direct property attribution, independent of cost centers
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vat_rate_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vat_rates.id"), nullable=True)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    journal_entry: Mapped["JournalEntry"] = relationship(back_populates="lines", foreign_keys=[journal_entry_id])
    account: Mapped["ChartOfAccount"] = relationship(foreign_keys=[account_id])
    cost_center: Mapped[Optional["CostCenter"]] = relationship(foreign_keys=[cost_center_id])
    vat_rate: Mapped[Optional["VatRate"]] = relationship(foreign_keys=[vat_rate_id])
    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821

    @property
    def account_code(self) -> Optional[str]:
        return self.account.account_code if self.account else None

    @property
    def account_name(self) -> Optional[str]:
        return self.account.account_name if self.account else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None
