"""
Financial Management module (Phase 8).

Design note: rather than building separate near-identical tables for
Tenant Payments, Owner Payments, Expenses, Income, Deposits, Refunds, and
Transfers, this phase uses a single unified ledger table (`Transaction`)
with a `transaction_type` discriminator — the same reasoning applied to
Owner (Phase 2), Property (Phase 4), and Tenant (Phase 6): these concepts
share the overwhelming majority of fields (amount, account, date,
description) and only differ in which counterparty they reference and how
they affect account balances. This also makes "Outstanding Balance" and
account-balance computation trivial: everything is one ledger, summed by
account or by counterparty.

A Transfer between two accounts is recorded as TWO linked Transaction rows
(a `transfer_out` from the source account and a `transfer_in` to the
destination account, linked via `transfer_pair_id`) rather than one row
with two account references — this keeps per-account balance math a
simple "sum(in) - sum(out) for this account_id", with no special-casing.

Tenant Payments and Owner Payments optionally link back to a specific
Rental/Lease installment (Phase 7 / Phase 3) so that recording a payment
here can mark that installment paid — one source of truth instead of two
disconnected ledgers. "Outstanding Balance" is deliberately NOT a stored
table: it's computed at read time directly from RentalPaymentInstallment
(tenant side) and LeasePaymentInstallment (owner side), which already
track payment_status — so it can never go stale.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, Date, Text, Numeric, DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class AccountType:
    CASH = "cash"
    BANK = "bank"


class TransactionType:
    TENANT_PAYMENT = "tenant_payment"
    OWNER_PAYMENT = "owner_payment"
    EXPENSE = "expense"
    INCOME = "income"
    DEPOSIT_RECEIVED = "deposit_received"
    DEPOSIT_REFUND = "deposit_refund"
    REFUND = "refund"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    # Phase 17 — Owner Ledger & Recoverable Expense Engine. Deliberately
    # distinct from EXPENSE: money the company pays on an owner's behalf
    # is NOT a company operating expense (see docs/owner-ledger-engine.md)
    # and must never be reported/aggregated as one. OWNER_REIMBURSEMENT
    # is the inbound counterpart — the owner paying the company back.
    RECOVERABLE_EXPENSE = "recoverable_expense"
    OWNER_REIMBURSEMENT = "owner_reimbursement"
    # Phase 19 — Financial Engine. A tenant-side manual correction (see
    # adjustment_service.py) — direction is carried by which set it's
    # placed in below (INFLOW: a credit in the tenant's favor, the
    # common case for a goodwill adjustment/correction). A
    # debit-direction correction should use EXPENSE with a category tag
    # instead, same as any other outbound correction.
    ADJUSTMENT = "adjustment"

    INFLOW_TYPES = {TENANT_PAYMENT, INCOME, DEPOSIT_RECEIVED, TRANSFER_IN, OWNER_REIMBURSEMENT, ADJUSTMENT}
    OUTFLOW_TYPES = {OWNER_PAYMENT, EXPENSE, DEPOSIT_REFUND, REFUND, TRANSFER_OUT, RECOVERABLE_EXPENSE}


class TransactionDirection:
    IN = "in"
    OUT = "out"


class TransactionStatus:
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvoiceStatus:
    DRAFT = "draft"
    SENT = "sent"  # "Issued" in Rent Billing Engine terminology - kept as SENT for backward compatibility, see docs/rent-billing-engine.md
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOID = "void"


class FinancialAccount(BaseModel):
    __tablename__ = "financial_accounts"

    account_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # cash | bank
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    bank_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    iban: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("currencies.id"), nullable=True)
    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    gl_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chart_of_accounts.id"), nullable=True)  # Phase 10: links this Cash/Bank account to its GL ledger account for automatic posting

    gl_account: Mapped[Optional["ChartOfAccount"]] = relationship(foreign_keys=[gl_account_id])  # noqa: F821


class Transaction(BaseModel):
    __tablename__ = "transactions"

    transaction_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)  # in | out
    transaction_status: Mapped[str] = mapped_column(String(20), default=TransactionStatus.COMPLETED, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("financial_accounts.id"), nullable=False, index=True)
    transfer_pair_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("owners.id"), nullable=True, index=True)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)
    rental_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_contracts.id"), nullable=True)
    rental_installment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_payment_installments.id"), nullable=True)
    lease_agreement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lease_agreements.id"), nullable=True)
    lease_installment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lease_payment_installments.id"), nullable=True)

    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # free text for expense/income categorization
    payment_method: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # cash|bank_transfer|cheque|card|online
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    account: Mapped["FinancialAccount"] = relationship(foreign_keys=[account_id])
    transfer_pair: Mapped[Optional["Transaction"]] = relationship(remote_side="Transaction.id", foreign_keys=[transfer_pair_id])
    tenant: Mapped[Optional["Tenant"]] = relationship(foreign_keys=[tenant_id])  # noqa: F821
    owner: Mapped[Optional["Owner"]] = relationship(foreign_keys=[owner_id])  # noqa: F821
    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821
    receipt: Mapped[Optional["Receipt"]] = relationship(back_populates="transaction", uselist=False, cascade="all, delete-orphan")

    @property
    def tenant_display_name(self) -> Optional[str]:
        return self.tenant.display_name if self.tenant else None

    @property
    def owner_display_name(self) -> Optional[str]:
        return self.owner.display_name if self.owner else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def unit_number(self) -> Optional[str]:
        return self.property_ref.unit_number if self.property_ref else None


class Receipt(BaseModel):
    """Auto-issued proof-of-payment document for tenant_payment and
    owner_payment transactions. One receipt per transaction."""
    __tablename__ = "receipts"

    receipt_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), unique=True, nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Rent Billing Engine: when a payment settles a specific Invoice, the
    # auto-issued Receipt links back to it — this is the "Payment Receipt
    # is a separate document from the Rent Invoice, generated only after
    # payment" requirement, without inventing a new table for it.
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    print_count: Mapped[int] = mapped_column(Integer, default=0)

    transaction: Mapped["Transaction"] = relationship(back_populates="receipt", foreign_keys=[transaction_id])
    invoice: Mapped[Optional["Invoice"]] = relationship(foreign_keys=[invoice_id])


class Invoice(BaseModel):
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    rental_contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("rental_contracts.id"), nullable=True)
    property_id: Mapped[Optional[int]] = mapped_column(ForeignKey("properties.id"), nullable=True, index=True)  # Profit Center extension: links this invoice to a Property
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_status: Mapped[str] = mapped_column(String(20), default=InvoiceStatus.DRAFT, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id"), nullable=True)

    # ---------------- Rent Billing Engine additions ----------------
    # Billing cycle this invoice was generated under (mirrors the
    # contract's payment_frequency at generation time — RentalContract
    # already supports monthly/quarterly/semi_annual/annual/custom, see
    # RentalPaymentFrequency; this just records which one produced this
    # specific invoice, since the contract's own frequency could change
    # later while this invoice must not).
    billing_cycle: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    billing_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    billing_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    # Immutable data snapshot, frozen at generation time: tenant name/
    # address, property/building/unit, contract number, rent/fees/taxes/
    # discount breakdown, company info. Stays correct forever even if the
    # tenant moves, the property is renamed, or company details change —
    # exactly the "everything must remain unchanged forever" requirement.
    # Stored as JSON rather than a dozen new denormalized columns.
    snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Partial payment support: amount_paid accumulates across possibly
    # multiple part-payments; invoice_status becomes PARTIALLY_PAID
    # while 0 < amount_paid < amount, and PAID once amount_paid >= amount.
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    print_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # An opaque, non-sequential, non-sensitive token for the QR code's
    # verification URL (.../verify/{qr_token}) — deliberately NOT the
    # sequential invoice_number or the numeric id, so the QR code can't
    # be used to enumerate/guess other invoices.
    qr_token: Mapped[Optional[str]] = mapped_column(String(36), unique=True, nullable=True)

    tenant: Mapped["Tenant"] = relationship(foreign_keys=[tenant_id])  # noqa: F821
    property_ref: Mapped[Optional["Property"]] = relationship(foreign_keys=[property_id])  # noqa: F821

    @property
    def tenant_display_name(self) -> Optional[str]:
        return self.tenant.display_name if self.tenant else None

    @property
    def property_title(self) -> Optional[str]:
        return self.property_ref.title if self.property_ref else None

    @property
    def unit_number(self) -> Optional[str]:
        return self.property_ref.unit_number if self.property_ref else None

    @property
    def outstanding_amount(self) -> Decimal:
        return self.amount - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return self.invoice_status in (InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID) and self.due_date < date.today()
