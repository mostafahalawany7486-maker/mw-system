"""
Financial Engine API router.

IMPORTANT — path prefix: the spec lists these as `/financial/...`, but
the existing financial.py router (Phase 8, unmodified) already owns
`/financial` with its own `/dashboard` and `/transfers` sub-paths.
Mounting a second router at the exact same prefix with colliding
sub-paths would silently shadow whichever one FastAPI happens to match
first — a direct violation of "DO NOT break existing APIs." This
router is mounted at `/financial-engine` instead; every operation the
spec's API section asks for is still present, just under a prefix that
can't collide with the pre-existing one. See docs/financial-engine.md.

Beyond the spec's literal 9 endpoints, a handful of supporting deposit-
lifecycle endpoints were added (deduction/forfeit/transfer-to-owner
have no other reachable path otherwise) plus GET /dashboard and
GET /deposits/{contract_type}/{contract_id} for the summary/history
views a real UI needs.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import PermissionChecker
from app.schemas.financial_engine import (
    DepositCreateRequest, DepositActionRequest, RefundRequest, AdjustmentRequest, TransferRequest,
    AllLedgersSummaryOut, CompanyLedgerOut, OwnerLedgerSummaryOut, TenantLedgerOut, PropertyScopedLedgerOut,
    DepositSummaryOut, TransferResultOut, FinancialEngineDashboardOut,
)
from app.business_workflows.financial_engine.financial_engine import FinancialEngine
from app.models.user import User

router = APIRouter(prefix="/financial-engine", tags=["Financial Engine"])


# ---------------- Ledgers ----------------
@router.get("/ledgers", response_model=AllLedgersSummaryOut)
def get_all_ledgers(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_all_ledgers_summary()


@router.get("/company", response_model=CompanyLedgerOut)
def get_company_ledger(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_company_ledger()


@router.get("/owners/{owner_id}", response_model=OwnerLedgerSummaryOut)
def get_owner_ledger(owner_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_owner_ledger(owner_id)


@router.get("/tenants/{tenant_id}", response_model=TenantLedgerOut)
def get_tenant_ledger(tenant_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_tenant_ledger(tenant_id)


@router.get("/buildings/{building_id}", response_model=PropertyScopedLedgerOut)
def get_building_ledger(building_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_building_ledger(building_id)


@router.get("/properties/{property_id}", response_model=PropertyScopedLedgerOut)
def get_property_ledger(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_property_ledger(property_id)


@router.get("/units/{unit_id}", response_model=PropertyScopedLedgerOut)
def get_unit_ledger(unit_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_unit_ledger(unit_id)


# ---------------- Dashboard ----------------
@router.get("/dashboard", response_model=FinancialEngineDashboardOut)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).get_dashboard()


# ---------------- Deposits ----------------
@router.post("/deposit", status_code=201)
def create_deposit(payload: DepositCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    engine = FinancialEngine(db)
    result = engine.create_deposit(payload.contract_type, payload.contract_id, payload.amount, payload.account_id, payload.payment_date, current_user.id, payload.reference_number)
    return {"transaction_id": result["transaction"].id, "ledger_entry_id": result["ledger_entry"].id, "balance_after": result["ledger_entry"].balance_after}


@router.get("/deposits/{contract_type}/{contract_id}", response_model=DepositSummaryOut)
def get_deposit_summary(contract_type: str, contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).deposits.get_summary(contract_type, contract_id)


@router.post("/deposits/{contract_type}/{contract_id}/deduct")
def deduct_deposit(contract_type: str, contract_id: int, payload: DepositActionRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    engine = FinancialEngine(db)
    result = engine.deposits.deduct_deposit(contract_type, contract_id, payload.amount, payload.reason or "", current_user.id)
    return {"ledger_entry_id": result["ledger_entry"].id, "balance_after": result["ledger_entry"].balance_after}


@router.post("/deposits/{contract_type}/{contract_id}/forfeit")
def forfeit_deposit(contract_type: str, contract_id: int, payload: DepositActionRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    engine = FinancialEngine(db)
    result = engine.deposits.forfeit_deposit(contract_type, contract_id, payload.reason or "", current_user.id)
    return {"ledger_entry_id": result["ledger_entry"].id, "balance_after": result["ledger_entry"].balance_after}


@router.post("/deposits/{contract_type}/{contract_id}/transfer-to-owner")
def transfer_deposit_to_owner(contract_type: str, contract_id: int, payload: DepositActionRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    engine = FinancialEngine(db)
    result = engine.deposits.transfer_to_owner(contract_type, contract_id, payload.amount, payload.owner_id, current_user.id, payload.reason)
    return {"owner_ledger_entry_id": result["owner_ledger_entry"].id, "balance_after": result["deposit_ledger_entry"].balance_after}


@router.get("/deposits/{contract_type}/{contract_id}/verify")
def verify_deposit_ledger(contract_type: str, contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.view"))):
    return FinancialEngine(db).sync.verify_deposit_ledger(contract_type, contract_id)


# ---------------- Refunds ----------------
@router.post("/refund", status_code=201)
def create_refund(payload: RefundRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    engine = FinancialEngine(db)
    kwargs = payload.model_dump(exclude={"refund_type"})
    result = engine.create_refund(payload.refund_type, current_user.id, **kwargs)
    if result["refund_type"] == "payment":
        return {"refund_type": "payment", "payment_id": result["payment"].id, "payment_status": result["payment"].payment_status}
    return {"refund_type": "deposit", "ledger_entry_id": result["ledger_entry"].id, "balance_after": result["ledger_entry"].balance_after}


# ---------------- Adjustments ----------------
@router.post("/adjustment", status_code=201)
def create_adjustment(payload: AdjustmentRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    engine = FinancialEngine(db)
    result = engine.create_adjustment(payload.scope, payload.entity_id, payload.amount, payload.description, current_user.id, payload.is_credit, payload.account_id, payload.property_id)
    if result["scope"] == "owner":
        return {"scope": "owner", "entry_id": result["entry"].id, "balance": result["entry"].balance}
    return {"scope": "tenant", "transaction_id": result["transaction"].id}


# ---------------- Transfer ----------------
@router.post("/transfer", response_model=TransferResultOut, status_code=201)
def create_transfer(payload: TransferRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    return FinancialEngine(db).create_transfer(
        payload.from_account_id, payload.to_account_id, payload.amount, payload.transaction_date,
        current_user.id, payload.description, payload.reference_number,
    )
