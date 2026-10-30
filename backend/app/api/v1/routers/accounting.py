from math import ceil
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.accounting import (
    ChartOfAccountCreate, ChartOfAccountUpdate, ChartOfAccountOut,
    CostCenterCreate, CostCenterUpdate, CostCenterOut,
    VatRateCreate, VatRateUpdate, VatRateOut,
    PostingRuleCreate, PostingRuleUpdate, PostingRuleOut,
    JournalEntryCreate, JournalEntryUpdate, JournalEntryListItemOut, JournalEntryDetailOut,
    TrialBalanceOut, GeneralLedgerOut, BalanceSheetOut, IncomeStatementOut, CashFlowOut, VatReportOut,
)
from app.services.accounting_service import (
    ChartOfAccountService, CostCenterService, VatRateService, PostingRuleService,
    JournalEntryService, AccountingReportService,
)
from app.models.user import User

router = APIRouter(prefix="/accounting", tags=["Accounting"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Chart of Accounts ----------------
@router.get("/chart-of-accounts", response_model=list[ChartOfAccountOut])
def list_chart_of_accounts(
    account_type: Optional[str] = Query(None), with_balances: bool = Query(False),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return ChartOfAccountService(db).list_accounts(account_type, with_balances)


@router.post("/chart-of-accounts", response_model=ChartOfAccountOut, status_code=201)
def create_account(payload: ChartOfAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.create"))):
    return ChartOfAccountService(db).create_account(payload.model_dump(), actor_id=current_user.id)


@router.get("/chart-of-accounts/{account_id}", response_model=ChartOfAccountOut)
def get_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return ChartOfAccountService(db).get_account(account_id)


@router.put("/chart-of-accounts/{account_id}", response_model=ChartOfAccountOut)
def update_account(account_id: int, payload: ChartOfAccountUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return ChartOfAccountService(db).update_account(account_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/chart-of-accounts/{account_id}", response_model=MessageResponse)
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.delete"))):
    ChartOfAccountService(db).delete_account(account_id, actor_id=current_user.id)
    return {"message": "Account deleted successfully"}


# ---------------- Cost Centers ----------------
@router.get("/cost-centers", response_model=list[CostCenterOut])
def list_cost_centers(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return CostCenterService(db).list_cost_centers()


@router.post("/cost-centers", response_model=CostCenterOut, status_code=201)
def create_cost_center(payload: CostCenterCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.create"))):
    return CostCenterService(db).create_cost_center(payload.model_dump(), actor_id=current_user.id)


@router.get("/cost-centers/{cost_center_id}", response_model=CostCenterOut)
def get_cost_center(cost_center_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return CostCenterService(db).get_cost_center(cost_center_id)


@router.put("/cost-centers/{cost_center_id}", response_model=CostCenterOut)
def update_cost_center(cost_center_id: int, payload: CostCenterUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return CostCenterService(db).update_cost_center(cost_center_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/cost-centers/{cost_center_id}", response_model=MessageResponse)
def delete_cost_center(cost_center_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.delete"))):
    CostCenterService(db).delete_cost_center(cost_center_id, actor_id=current_user.id)
    return {"message": "Cost center deleted successfully"}


# ---------------- VAT Rates ----------------
@router.get("/vat-rates", response_model=list[VatRateOut])
def list_vat_rates(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return VatRateService(db).list_rates()


@router.post("/vat-rates", response_model=VatRateOut, status_code=201)
def create_vat_rate(payload: VatRateCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.create"))):
    return VatRateService(db).create_rate(payload.model_dump(), actor_id=current_user.id)


@router.put("/vat-rates/{rate_id}", response_model=VatRateOut)
def update_vat_rate(rate_id: int, payload: VatRateUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return VatRateService(db).update_rate(rate_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/vat-rates/{rate_id}", response_model=MessageResponse)
def delete_vat_rate(rate_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.delete"))):
    VatRateService(db).delete_rate(rate_id, actor_id=current_user.id)
    return {"message": "VAT rate deleted successfully"}


# ---------------- Posting Rules (Automatic Posting configuration) ----------------
@router.get("/posting-rules", response_model=list[PostingRuleOut])
def list_posting_rules(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return PostingRuleService(db).list_rules()


@router.post("/posting-rules", response_model=PostingRuleOut, status_code=201)
def create_posting_rule(payload: PostingRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.create"))):
    return PostingRuleService(db).create_rule(payload.model_dump(), actor_id=current_user.id)


@router.put("/posting-rules/{rule_id}", response_model=PostingRuleOut)
def update_posting_rule(rule_id: int, payload: PostingRuleUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return PostingRuleService(db).update_rule(rule_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/posting-rules/{rule_id}", response_model=MessageResponse)
def delete_posting_rule(rule_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.delete"))):
    PostingRuleService(db).delete_rule(rule_id, actor_id=current_user.id)
    return {"message": "Posting rule deleted successfully"}


# ---------------- Journal Entries ----------------
@router.get("/journal-entries", response_model=PaginatedResponse[JournalEntryListItemOut])
def list_journal_entries(
    params: PaginationParams = Depends(get_pagination_params),
    entry_status: Optional[str] = Query(None), source_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    items, total = JournalEntryService(db).list_entries(params, entry_status, source_type, date_from, date_to)
    return _paginated(items, total, params)


@router.post("/journal-entries", response_model=JournalEntryDetailOut, status_code=201)
def create_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.create"))):
    return JournalEntryService(db).create_entry(payload.model_dump(), actor_id=current_user.id)


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryDetailOut)
def get_journal_entry(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return JournalEntryService(db).get_entry(entry_id)


@router.put("/journal-entries/{entry_id}", response_model=JournalEntryDetailOut)
def update_journal_entry(entry_id: int, payload: JournalEntryUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return JournalEntryService(db).update_entry(entry_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/journal-entries/{entry_id}", response_model=MessageResponse)
def delete_journal_entry(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.delete"))):
    JournalEntryService(db).delete_entry(entry_id, actor_id=current_user.id)
    return {"message": "Journal entry deleted successfully"}


@router.post("/journal-entries/{entry_id}/post", response_model=JournalEntryDetailOut)
def post_journal_entry(entry_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return JournalEntryService(db).post_entry(entry_id, actor_id=current_user.id)


@router.post("/journal-entries/{entry_id}/reverse", response_model=JournalEntryDetailOut)
def reverse_journal_entry(entry_id: int, reversal_date: date = Query(...), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.edit"))):
    return JournalEntryService(db).reverse_entry(entry_id, reversal_date, actor_id=current_user.id)


# ---------------- Reports ----------------
@router.get("/reports/trial-balance", response_model=TrialBalanceOut)
def trial_balance(as_of_date: date = Query(...), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return AccountingReportService(db).trial_balance(as_of_date)


@router.get("/reports/general-ledger", response_model=GeneralLedgerOut)
def general_ledger(
    account_id: int = Query(...), date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).general_ledger(account_id, date_from, date_to)


@router.get("/reports/balance-sheet", response_model=BalanceSheetOut)
def balance_sheet(as_of_date: date = Query(...), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view"))):
    return AccountingReportService(db).balance_sheet(as_of_date)


@router.get("/reports/income-statement", response_model=IncomeStatementOut)
def income_statement(
    date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).income_statement(date_from, date_to)


@router.get("/reports/cash-flow", response_model=CashFlowOut)
def cash_flow(
    date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).cash_flow(date_from, date_to)


@router.get("/reports/vat", response_model=VatReportOut)
def vat_report(
    date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).vat_report(date_from, date_to)
