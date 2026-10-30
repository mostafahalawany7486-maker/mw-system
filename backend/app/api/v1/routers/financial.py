from math import ceil
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.financial import (
    FinancialAccountCreate, FinancialAccountUpdate, FinancialAccountOut,
    TransactionCreate, TransactionUpdate, TransactionOut, TransferCreate,
    ReceiptOut, InvoiceCreate, InvoiceUpdate, InvoiceOut, RecordInvoicePaymentRequest,
    OutstandingBalanceOut, FinancialDashboardOut,
    GenerateBulkInvoicesRequest, ApproveInvoicesRequest, BulkPrintRequest,
    InvoicePrintOut, InvoiceVerificationOut, VoidCancelInvoiceRequest,
)
from app.services.financial_service import FinancialAccountService, FinancialService
from app.models.financial import InvoiceStatus
from app.models.user import User

router = APIRouter(prefix="/financial", tags=["Financial Management"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard & Outstanding Balances ----------------
@router.get("/dashboard/summary", response_model=FinancialDashboardOut)
def financial_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).dashboard()


@router.get("/outstanding-balances", response_model=OutstandingBalanceOut)
def outstanding_balances(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).outstanding_balances()


@router.post("/maintenance/run")
def run_maintenance(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    """On-demand: marks sent invoices past their due date as overdue."""
    return FinancialService(db).maintenance_sweep(actor_id=current_user.id)


# ---------------- Financial Accounts (Cash & Bank) ----------------
@router.get("/accounts", response_model=PaginatedResponse[FinancialAccountOut])
def list_accounts(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    items, total = FinancialAccountService(db).list_accounts(params)
    return _paginated(items, total, params)


@router.post("/accounts", response_model=FinancialAccountOut, status_code=201)
def create_account(payload: FinancialAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    return FinancialAccountService(db).create_account(payload.model_dump(), actor_id=current_user.id)


@router.get("/accounts/{account_id}", response_model=FinancialAccountOut)
def get_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialAccountService(db).get_account(account_id)


@router.put("/accounts/{account_id}", response_model=FinancialAccountOut)
def update_account(account_id: int, payload: FinancialAccountUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialAccountService(db).update_account(account_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/accounts/{account_id}", response_model=MessageResponse)
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.delete"))):
    FinancialAccountService(db).delete_account(account_id, actor_id=current_user.id)
    return {"message": "Account deleted successfully"}


# ---------------- Transactions (Tenant/Owner Payments, Expenses, Income, Deposits, Refunds) ----------------
@router.get("/transactions", response_model=PaginatedResponse[TransactionOut])
def list_transactions(
    params: PaginationParams = Depends(get_pagination_params),
    transaction_type: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    tenant_id: Optional[int] = Query(None),
    owner_id: Optional[int] = Query(None),
    property_id: Optional[int] = Query(None),
    building_id: Optional[int] = Query(None, description="Filter to a building's own transactions plus every one of its units"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("financial.view")),
):
    items, total = FinancialService(db).list_transactions(params, transaction_type, account_id, tenant_id, owner_id, date_from, date_to, property_id, building_id)
    return _paginated(items, total, params)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    return FinancialService(db).create_transaction(payload.model_dump(), actor_id=current_user.id)


@router.get("/transactions/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).get_transaction(transaction_id)


@router.put("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, payload: TransactionUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialService(db).update_transaction(transaction_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/transactions/{transaction_id}", response_model=MessageResponse)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.delete"))):
    FinancialService(db).delete_transaction(transaction_id, actor_id=current_user.id)
    return {"message": "Transaction deleted successfully"}


# ---------------- Transfers ----------------
@router.post("/transfers")
def create_transfer(payload: TransferCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    return FinancialService(db).create_transfer(payload.model_dump(), actor_id=current_user.id)


# ---------------- Receipts (auto-issued, read-only) ----------------
@router.get("/receipts", response_model=PaginatedResponse[ReceiptOut])
def list_receipts(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    items, total = FinancialService(db).list_receipts(params)
    return _paginated(items, total, params)


@router.get("/receipts/{receipt_id}", response_model=ReceiptOut)
def get_receipt(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).get_receipt(receipt_id)


# ---------------- Receipt printing (tenant_payment + owner_payment) ----------------
# The generic counterpart to the Rent Voucher print module — raised
# directly: an Owner Payment previously had no printable document at
# all, just an internal RCP-xxx reference with nothing to hand the
# owner to sign.
@router.get("/receipts/{receipt_id}/print-data")
def get_receipt_print_data(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).get_receipt_print_data(receipt_id)


@router.post("/receipts/{receipt_id}/print", response_model=ReceiptOut)
def record_receipt_print(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).record_receipt_print(receipt_id, actor_id=current_user.id)


# ---------------- Invoices ----------------
@router.get("/invoices", response_model=PaginatedResponse[InvoiceOut])
def list_invoices(
    params: PaginationParams = Depends(get_pagination_params),
    invoice_status: Optional[str] = Query(None),
    tenant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("financial.view")),
):
    items, total = FinancialService(db).list_invoices(params, invoice_status, tenant_id)
    return _paginated(items, total, params)


@router.post("/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    return FinancialService(db).create_invoice(payload.model_dump(), actor_id=current_user.id)


# ---------------- Rent Billing Engine: bulk operations & search ----------------
# Registered here (before /invoices/{invoice_id}) for the same reason
# established in the Rental Receipt Module: a single dynamic
# {invoice_id} segment would otherwise swallow these as an invoice ID.
@router.post("/invoices/bulk-generate", response_model=list[InvoiceOut])
def generate_bulk_invoices(payload: GenerateBulkInvoicesRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    """'Automatic Invoice Generation' — manually triggered (no scheduler
    exists in this codebase; same documented decision as the Rental
    Receipt Module). Scans every active contract (optionally scoped to a
    building/property/owner via property_ids) and generates one DRAFT
    invoice per contract for the given billing period, using each
    contract's own billing cycle — never a duplicate for the same
    (contract, period)."""
    return FinancialService(db).generate_bulk_invoices(payload.billing_period_start, payload.property_ids, actor_id=current_user.id)


@router.post("/invoices/bulk-approve", response_model=list[InvoiceOut])
def approve_invoices(payload: ApproveInvoicesRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    """'Invoice Approval' step — draft -> sent for every invoice id
    given, e.g. an entire batch generated together."""
    return FinancialService(db).approve_invoices(payload.invoice_ids, actor_id=current_user.id)


@router.post("/invoices/bulk-print", response_model=list[InvoicePrintOut])
def bulk_print_invoices(payload: BulkPrintRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    """Backs 'Print Selected' / 'Print Entire Building' / 'Print Entire
    Property' / 'Print Entire Owner' / 'Print Entire Month' / 'Print
    Entire Billing Cycle' — all of these reduce to "here is a list of
    invoice ids" by the time they reach this endpoint; the filtering
    that produces that list is GET /invoices/search below."""
    return FinancialService(db).get_bulk_print_data(payload.invoice_ids, actor_id=current_user.id)


@router.get("/invoices/search", response_model=PaginatedResponse[InvoiceOut])
def search_invoices(
    params: PaginationParams = Depends(get_pagination_params),
    invoice_number: Optional[str] = Query(None), tenant_id: Optional[int] = Query(None), property_id: Optional[int] = Query(None),
    owner_id: Optional[int] = Query(None), rental_contract_id: Optional[int] = Query(None),
    phone: Optional[str] = Query(None), civil_id: Optional[str] = Query(None), invoice_status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view")),
):
    items, total = FinancialService(db).search_invoices(
        params, invoice_number, tenant_id, property_id, owner_id, rental_contract_id, phone, civil_id, invoice_status, date_from, date_to,
    )
    return _paginated(items, total, params)


@router.get("/invoices/verify/{qr_token}", response_model=InvoiceVerificationOut)
def verify_invoice(qr_token: str, db: Session = Depends(get_db)):
    """The QR code's public verification endpoint — deliberately no
    PermissionChecker, since anyone holding a printed invoice should be
    able to confirm it's genuine by scanning it. Returns only
    invoice_number/issue_date/status — no amounts, no tenant details."""
    invoice = FinancialService(db).get_invoice_by_qr_token(qr_token)
    return {
        "invoice_number": invoice.invoice_number, "issue_date": invoice.issue_date,
        "invoice_status": invoice.invoice_status, "is_valid": invoice.invoice_status != InvoiceStatus.VOID,
    }


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialService(db).get_invoice(invoice_id)


@router.put("/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, payload: InvoiceUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialService(db).update_invoice(invoice_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.post("/invoices/{invoice_id}/send", response_model=InvoiceOut)
def send_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialService(db).send_invoice(invoice_id, actor_id=current_user.id)


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialService(db).cancel_invoice(invoice_id, actor_id=current_user.id)


@router.post("/invoices/{invoice_id}/record-payment", response_model=InvoiceOut)
def record_invoice_payment(invoice_id: int, payload: RecordInvoicePaymentRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialService(db).record_invoice_payment(
        invoice_id, payload.account_id, payload.payment_method, payload.reference_number, payload.transaction_date,
        actor_id=current_user.id, amount=payload.amount,
    )


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceOut)
def void_invoice(invoice_id: int, payload: VoidCancelInvoiceRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    """Distinct from /cancel: invoices are never deleted, only voided or
    cancelled (see spec). A reason is mandatory here, unlike /cancel
    which stays optional for backward compatibility with the endpoint
    that already existed before the Rent Billing Engine."""
    return FinancialService(db).void_invoice(invoice_id, payload.reason, actor_id=current_user.id)


@router.post("/invoices/{invoice_id}/print", response_model=InvoicePrintOut)
def print_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    """Records the print/reprint (see spec's Reprint Management —
    user/date/reason captured via ActivityLog's actor_id/created_at;
    IP is captured the same way every other audited action in this
    codebase captures it, via AuditLog, not duplicated here) and returns
    the printable DTO in the same call."""
    service = FinancialService(db)
    service.record_invoice_print(invoice_id, actor_id=current_user.id)
    return service.get_invoice_print_data(invoice_id)


@router.get("/invoices/{invoice_id}/print-data", response_model=InvoicePrintOut)
def get_invoice_print_data(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    """Preview endpoint — fetches the printable DTO WITHOUT incrementing
    print_count (see POST .../print above for the version that does),
    for 'Print Preview' before actually committing to a print."""
    return FinancialService(db).get_invoice_print_data(invoice_id)


@router.post("/invoices/{invoice_id}/deliver", response_model=InvoiceOut)
def mark_invoice_delivered(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    return FinancialService(db).mark_invoice_delivered(invoice_id, actor_id=current_user.id)
