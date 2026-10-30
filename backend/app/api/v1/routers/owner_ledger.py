"""
Owner Ledger & Recoverable Expense Engine API router. Thin — every
endpoint delegates straight to the relevant service in
app/business_workflows/owner_ledger/.

No `prefix=` at the router level (unlike every other router in this
codebase) because the spec's own requested API surface spans two
different top-level paths — `/owner-ledger/...` and
`/owner-statement/{owner_id}` — so each route below states its full
path explicitly instead.

Permission mapping (matches the existing 'module.action' convention in
seed.py): owner_ledger.view for reads, owner_ledger.create for posting
new entries/expenses/reimbursements, owner_ledger.edit for reversing an
entry — mirrors the same pattern every other module in this codebase
already uses.

Two endpoints beyond the spec's literal minimum list were added since
the spec's own "OWNER DASHBOARD" and "AUDIT" sections otherwise have no
way to be reached via the API at all: `GET /owner-ledger/{owner_id}/dashboard`
and `POST /owner-ledger/{entry_id}/reverse`.
"""
from typing import Optional
from math import ceil
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse
from app.schemas.owner_ledger import (
    OwnerLedgerEntryCreate, RecoverableExpenseCreate, RecoveredPaymentCreate, ReverseEntryRequest, PayOwnerRequest,
    OwnerLedgerEntryOut, OwnerBalanceOut, OwnerDashboardOut, OwnerStatementOut,
)
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService
from app.business_workflows.owner_ledger.recoverable_expense_service import RecoverableExpenseService
from app.business_workflows.owner_ledger.owner_balance_service import OwnerBalanceService
from app.business_workflows.owner_ledger.owner_statement_service import OwnerStatementService
from app.business_workflows.owner_ledger.owner_settlement_service import OwnerLedgerSettlementService
from app.repositories.owner_ledger_repository import OwnerLedgerRepository
from app.models.user import User

router = APIRouter(tags=["Owner Ledger & Recoverable Expense Engine"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Manual entries ----------------
@router.post("/owner-ledger", response_model=OwnerLedgerEntryOut, status_code=201)
def create_ledger_entry(payload: OwnerLedgerEntryCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.create"))):
    service = OwnerLedgerService(db)
    return service.post_entry(
        owner_id=payload.owner_id, transaction_date=payload.transaction_date, transaction_type=payload.transaction_type,
        description=payload.description, actor_id=current_user.id, debit=payload.debit, credit=payload.credit,
        property_id=payload.property_id, reference_type="manual",
    )


@router.get("/owner-ledger", response_model=PaginatedResponse[OwnerLedgerEntryOut])
def list_all_ledger_entries(
    params: PaginationParams = Depends(get_pagination_params),
    owner_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("owner_ledger.view")),
):
    from datetime import date as _date
    df = _date.fromisoformat(date_from) if date_from else None
    dt = _date.fromisoformat(date_to) if date_to else None
    items, total = OwnerLedgerRepository(db).list_all(params.page, params.page_size, owner_id, transaction_type, df, dt)
    return _paginated(items, total, params)


@router.get("/owner-ledger/{owner_id}", response_model=PaginatedResponse[OwnerLedgerEntryOut])
def list_ledger_for_owner(
    owner_id: int,
    params: PaginationParams = Depends(get_pagination_params),
    transaction_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("owner_ledger.view")),
):
    from datetime import date as _date
    df = _date.fromisoformat(date_from) if date_from else None
    dt = _date.fromisoformat(date_to) if date_to else None
    items, total = OwnerLedgerRepository(db).list_for_owner(owner_id, params.page, params.page_size, transaction_type, df, dt, params.sort_dir or "desc")
    return _paginated(items, total, params)


@router.get("/owner-ledger/{owner_id}/balance", response_model=OwnerBalanceOut)
def get_owner_balance(owner_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.view"))):
    return OwnerBalanceService(db).get_owner_balance_summary(owner_id)


@router.get("/owner-ledger/{owner_id}/dashboard", response_model=OwnerDashboardOut)
def get_owner_dashboard(owner_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.view"))):
    return OwnerBalanceService(db).get_dashboard(owner_id)


# ---------------- Recoverable expenses ----------------
@router.post("/owner-ledger/recoverable-expense", response_model=OwnerLedgerEntryOut, status_code=201)
def create_recoverable_expense(payload: RecoverableExpenseCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.create"))):
    result = RecoverableExpenseService(db).create_recoverable_expense(
        owner_id=payload.owner_id, account_id=payload.account_id, amount=payload.amount,
        expense_category=payload.expense_category, description=payload.description, payment_date=payload.payment_date,
        actor_id=current_user.id, property_id=payload.property_id, reference_number=payload.reference_number,
    )
    return result["ledger_entry"]


@router.post("/owner-ledger/recovered-payment", response_model=OwnerLedgerEntryOut, status_code=201)
def create_recovered_payment(payload: RecoveredPaymentCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.create"))):
    result = RecoverableExpenseService(db).record_recovered_payment(
        owner_id=payload.owner_id, account_id=payload.account_id, amount=payload.amount,
        payment_method=payload.payment_method, payment_date=payload.payment_date, actor_id=current_user.id,
        property_id=payload.property_id, reference_number=payload.reference_number, notes=payload.notes,
    )
    return result["ledger_entry"]


# ---------------- Pay Owner (general balance settlement, not tied to
# any one Lease installment — the counterpart to
# /leases/{id}/installments/{id}/settle for the common case where the
# ledger's Rental Income wasn't posted through a Master Lease
# installment in the first place) ----------------
@router.post("/owner-ledger/{owner_id}/pay")
def pay_owner(owner_id: int, payload: PayOwnerRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.create"))):
    result = OwnerLedgerSettlementService(db).pay_owner_balance(
        owner_id, payload.amount, payload.account_id, payload.transaction_date, actor_id=current_user.id,
        payment_method=payload.payment_method, reference_number=payload.reference_number,
    )
    return {
        "message": "Owner paid — transaction recorded and Owner Ledger updated.",
        "transaction_id": result["transaction_id"],
        "new_balance": result["new_balance"],
        "receipt_id": result["receipt_id"],
    }


# ---------------- Reversal (audit: "only reversal entries are allowed") ----------------
@router.post("/owner-ledger/{entry_id}/reverse", response_model=OwnerLedgerEntryOut)
def reverse_ledger_entry(entry_id: int, payload: ReverseEntryRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.edit"))):
    return OwnerLedgerService(db).reverse_entry(entry_id, payload.reason, actor_id=current_user.id, reversal_date=payload.reversal_date)


# ---------------- Owner Statement ----------------
@router.get("/owner-statement/{owner_id}", response_model=OwnerStatementOut)
def get_owner_statement(
    owner_id: int, date_from: str = Query(...), date_to: str = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owner_ledger.view")),
):
    from datetime import date as _date
    return OwnerStatementService(db).generate_statement(owner_id, _date.fromisoformat(date_from), _date.fromisoformat(date_to))
