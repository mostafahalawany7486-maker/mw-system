from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.rental import (
    RentalContractCreate, RentalContractUpdate, RentalContractListItemOut, RentalContractDetailOut,
    TerminateRentalRequest, RenewRentalRequest, GenerateScheduleRequest,
    RentalInstallmentCreate, RentalInstallmentUpdate, RentalInstallmentOut,
    RentalDashboardOut,
    GenerateMonthlyReceiptsRequest, RentalReceiptOut, PaymentConfirmationIn, RentalReceiptSearchItemOut,
)
from app.services.rental_service import RentalService
from app.models.user import User

router = APIRouter(prefix="/rentals", tags=["Rental Contracts"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard & Maintenance ----------------
@router.get("/dashboard/summary", response_model=RentalDashboardOut)
def rental_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.view"))):
    return RentalService(db).dashboard()


@router.post("/maintenance/run")
def run_maintenance(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    """On-demand housekeeping: auto-expires overdue contracts, flags overdue
    installments, assesses late fees past grace period, and sends renewal
    reminders. See docs/phase3-renewal-reminders.md for wiring this to a
    real scheduler in production."""
    return RentalService(db).run_maintenance_sweep(actor_id=current_user.id)


# ---------------- Rental Receipt Module ----------------
# Registered here (before /{contract_id}) for the same reason
# /dashboard/summary and /maintenance/run are: a single dynamic
# {contract_id} segment would otherwise swallow "receipts" as a
# contract ID. See docs/rental-receipt-module.md for the full design.
@router.post("/receipts/generate-monthly", response_model=list[RentalInstallmentOut])
def generate_monthly_receipts(payload: GenerateMonthlyReceiptsRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.create"))):
    """'Beginning of the month' trigger — manually invoked (no scheduler
    exists in this codebase; see Phase 1 analysis). Assigns a receipt
    number to every installment due in the given month for an active
    lease that doesn't already have one."""
    return RentalService(db).generate_monthly_receipts(payload.year, payload.month, actor_id=current_user.id)


@router.get("/receipts/search", response_model=PaginatedResponse[RentalReceiptSearchItemOut])
def search_receipts(
    receipt_number: Optional[str] = Query(None), tenant_id: Optional[int] = Query(None), property_id: Optional[int] = Query(None),
    rental_month: Optional[str] = Query(None, description="YYYY-MM"), date_from: Optional[str] = Query(None), date_to: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None), reference_number: Optional[str] = Query(None),
    params: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.view")),
):
    from datetime import date as date_cls
    d_from = date_cls.fromisoformat(date_from) if date_from else None
    d_to = date_cls.fromisoformat(date_to) if date_to else None
    items, total = RentalService(db).search_receipts(
        params, receipt_number, tenant_id, property_id, rental_month, d_from, d_to, payment_method, reference_number,
    )
    out_items = [{
        "installment_id": i.id, "receipt_number": i.receipt_number,
        "tenant_display_name": i.contract.tenant_display_name if i.contract else None,
        "property_title": i.contract.property_title if i.contract else None,
        "unit_number": i.contract.unit_number if i.contract else None,
        "due_date": i.due_date, "amount": i.total_payable, "payment_status": i.payment_status,
        "payment_method": i.payment_method, "reference_number": i.reference_number, "print_count": i.print_count,
    } for i in items]
    return _paginated(out_items, total, params)


@router.get("/installments/{installment_id}/receipt", response_model=RentalReceiptOut)
def get_rental_receipt(installment_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.view"))):
    return RentalService(db).get_receipt_document(installment_id)


@router.post("/installments/{installment_id}/receipt/print", response_model=RentalReceiptOut)
def print_rental_receipt(installment_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    """Called right before the browser print dialog opens — records the
    print/reprint for the audit trail without changing anything the
    receipt displays."""
    service = RentalService(db)
    service.record_print(installment_id, actor_id=current_user.id)
    return service.get_receipt_document(installment_id)


@router.post("/installments/{installment_id}/confirm-payment")
def confirm_receipt_payment(installment_id: int, payload: PaymentConfirmationIn, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.edit"))):
    """The only action that makes a payment official — gated by
    financial.edit (not rentals.edit) to match the existing precedent set
    by POST /financial/invoices/{id}/record-payment, since both create a
    Transaction and post to the GL. Returns the installment plus
    transaction_id (added so CollectRentPage's Quick path — the only
    other caller that reads this response — can hand the transaction
    straight to /rent-vouchers/generate without a second lookup;
    RentalReceiptsPage, the original caller, ignores the response body
    entirely, so this is additive and doesn't change its behavior)."""
    installment, transaction_id = RentalService(db).confirm_payment(
        installment_id, payload.account_id, payload.payment_method, payload.reference_number,
        payload.transaction_date, payload.notes, actor_id=current_user.id,
    )
    return {**RentalInstallmentOut.model_validate(installment).model_dump(), "transaction_id": transaction_id}


# ---------------- Contract CRUD ----------------
@router.get("", response_model=PaginatedResponse[RentalContractListItemOut])
def list_contracts(
    params: PaginationParams = Depends(get_pagination_params),
    contract_status: Optional[str] = Query(None),
    tenant_id: Optional[int] = Query(None),
    property_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    expiring_soon: Optional[bool] = Query(None),
    include_archived: bool = Query(False, description="Include contracts archived via POST /rentals/{id}/archive (excluded by default)"),
    building_id: Optional[int] = Query(None, description="Show every contract under this building (matches the building itself or any of its child units)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("rentals.view")),
):
    items, total = RentalService(db).list_contracts(params, contract_status, tenant_id, property_id, branch_id, expiring_soon, include_archived, building_id)
    return _paginated(items, total, params)


@router.post("", response_model=RentalContractDetailOut, status_code=201)
def create_contract(payload: RentalContractCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.create"))):
    return RentalService(db).create_contract(payload.model_dump(), actor_id=current_user.id)


@router.get("/{contract_id}", response_model=RentalContractDetailOut)
def get_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.view"))):
    return RentalService(db).get_contract(contract_id)


@router.put("/{contract_id}", response_model=RentalContractDetailOut)
def update_contract(contract_id: int, payload: RentalContractUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).update_contract(contract_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{contract_id}", response_model=MessageResponse)
def delete_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.delete"))):
    RentalService(db).delete_contract(contract_id, actor_id=current_user.id)
    return {"message": "Rental contract deleted successfully"}


# ---------------- Archive (distinct from delete — see BaseRepository.archive()) ----------------
@router.post("/{contract_id}/archive", response_model=RentalContractDetailOut)
def archive_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).archive_contract(contract_id, actor_id=current_user.id)


@router.post("/{contract_id}/unarchive", response_model=RentalContractDetailOut)
def unarchive_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).unarchive_contract(contract_id, actor_id=current_user.id)


# ---------------- Status transitions ----------------
@router.post("/{contract_id}/activate", response_model=RentalContractDetailOut)
def activate_contract(contract_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).activate_contract(contract_id, actor_id=current_user.id)


@router.post("/{contract_id}/terminate", response_model=RentalContractDetailOut)
def terminate_contract(contract_id: int, payload: TerminateRentalRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).terminate_contract(contract_id, payload.terminated_date, payload.termination_reason, actor_id=current_user.id)


@router.post("/{contract_id}/renew", response_model=RentalContractDetailOut)
def renew_contract(contract_id: int, payload: RenewRentalRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).renew_contract(
        contract_id, payload.new_end_date, payload.new_start_date, payload.rent_amount, payload.notes_summary, actor_id=current_user.id
    )


# ---------------- Payment Schedule ----------------
@router.post("/{contract_id}/installments/generate", response_model=list[RentalInstallmentOut])
def generate_schedule(contract_id: int, payload: GenerateScheduleRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).generate_schedule(contract_id, payload.overwrite_existing, actor_id=current_user.id)


@router.post("/{contract_id}/installments", response_model=RentalInstallmentOut, status_code=201)
def add_installment(contract_id: int, payload: RentalInstallmentCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).add_installment(contract_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{contract_id}/installments/{installment_id}", response_model=RentalInstallmentOut)
def update_installment(contract_id: int, installment_id: int, payload: RentalInstallmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    return RentalService(db).update_installment(contract_id, installment_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{contract_id}/installments/{installment_id}", response_model=MessageResponse)
def delete_installment(contract_id: int, installment_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rentals.edit"))):
    RentalService(db).delete_installment(contract_id, installment_id, actor_id=current_user.id)
    return {"message": "Installment deleted successfully"}
