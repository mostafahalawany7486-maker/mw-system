from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.lease import (
    LeaseAgreementCreate, LeaseAgreementUpdate, LeaseAgreementListItemOut, LeaseAgreementDetailOut,
    TerminateLeaseRequest, RenewLeaseRequest, GenerateScheduleRequest,
    LeasePaymentInstallmentCreate, LeasePaymentInstallmentUpdate, LeasePaymentInstallmentOut,
    LeaseDashboardOut, SettleOwnerInstallmentRequest,
)
from app.services.lease_service import LeaseService
from app.models.user import User

router = APIRouter(prefix="/leases", tags=["Lease Agreements"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard & Maintenance ----------------
@router.get("/dashboard/summary", response_model=LeaseDashboardOut)
def lease_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.view"))):
    return LeaseService(db).dashboard()


@router.post("/maintenance/run")
def run_maintenance(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    """
    On-demand housekeeping: auto-expires overdue leases, flags overdue
    installments, and sends renewal reminder notifications. See
    docs/phase3-renewal-reminders.md for wiring this to a real scheduler.
    """
    return LeaseService(db).run_maintenance_sweep(actor_id=current_user.id)


# ---------------- Lease CRUD ----------------
@router.get("", response_model=PaginatedResponse[LeaseAgreementListItemOut])
def list_leases(
    params: PaginationParams = Depends(get_pagination_params),
    contract_status: Optional[str] = Query(None),
    owner_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    expiring_soon: Optional[bool] = Query(None),
    include_archived: bool = Query(False, description="Include leases archived via POST /leases/{id}/archive (excluded by default)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("leases.view")),
):
    items, total = LeaseService(db).list_leases(params, contract_status, owner_id, branch_id, expiring_soon, include_archived)
    return _paginated(items, total, params)


@router.post("", response_model=LeaseAgreementDetailOut, status_code=201)
def create_lease(payload: LeaseAgreementCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.create"))):
    return LeaseService(db).create_lease(payload.model_dump(), actor_id=current_user.id)


@router.get("/{lease_id}", response_model=LeaseAgreementDetailOut)
def get_lease(lease_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.view"))):
    return LeaseService(db).get_lease(lease_id)


@router.put("/{lease_id}", response_model=LeaseAgreementDetailOut)
def update_lease(lease_id: int, payload: LeaseAgreementUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).update_lease(lease_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{lease_id}", response_model=MessageResponse)
def delete_lease(lease_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.delete"))):
    LeaseService(db).delete_lease(lease_id, actor_id=current_user.id)
    return {"message": "Lease agreement deleted successfully"}


# ---------------- Archive (distinct from delete — see BaseRepository.archive()) ----------------
@router.post("/{lease_id}/archive", response_model=LeaseAgreementDetailOut)
def archive_lease(lease_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).archive_lease(lease_id, actor_id=current_user.id)


@router.post("/{lease_id}/unarchive", response_model=LeaseAgreementDetailOut)
def unarchive_lease(lease_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).unarchive_lease(lease_id, actor_id=current_user.id)


# ---------------- Status transitions ----------------
@router.post("/{lease_id}/activate", response_model=LeaseAgreementDetailOut)
def activate_lease(lease_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).activate_lease(lease_id, actor_id=current_user.id)


@router.post("/{lease_id}/terminate", response_model=LeaseAgreementDetailOut)
def terminate_lease(lease_id: int, payload: TerminateLeaseRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).terminate_lease(lease_id, payload.terminated_date, payload.termination_reason, actor_id=current_user.id)


@router.post("/{lease_id}/renew", response_model=LeaseAgreementDetailOut)
def renew_lease(lease_id: int, payload: RenewLeaseRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).renew_lease(
        lease_id, payload.new_end_date, payload.new_start_date, payload.rent_amount, payload.notes_summary, actor_id=current_user.id
    )


# ---------------- Payment Schedule ----------------
@router.post("/{lease_id}/installments/generate", response_model=list[LeasePaymentInstallmentOut])
def generate_schedule(lease_id: int, payload: GenerateScheduleRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).generate_schedule(lease_id, payload.overwrite_existing, actor_id=current_user.id)


@router.post("/{lease_id}/installments", response_model=LeasePaymentInstallmentOut, status_code=201)
def add_installment(lease_id: int, payload: LeasePaymentInstallmentCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).add_installment(lease_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{lease_id}/installments/{installment_id}", response_model=LeasePaymentInstallmentOut)
def update_installment(lease_id: int, installment_id: int, payload: LeasePaymentInstallmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    return LeaseService(db).update_installment(lease_id, installment_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{lease_id}/installments/{installment_id}", response_model=MessageResponse)
def delete_installment(lease_id: int, installment_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit"))):
    LeaseService(db).delete_installment(lease_id, installment_id, actor_id=current_user.id)
    return {"message": "Installment deleted successfully"}


# ---------------- Pay Owner (real settlement + Owner Ledger, together) ----------------
# The business logic for this already existed
# (OwnerLedgerSettlementService.settle_and_record, which itself delegates
# to the existing, unmodified Phase 12 OwnerSettlementWorkflowService for
# the actual payout) — it just had no API endpoint calling it yet. This
# is the only thing added here; neither service was changed.
@router.post("/{lease_id}/installments/{installment_id}/settle")
def settle_owner_installment(
    lease_id: int, installment_id: int, payload: SettleOwnerInstallmentRequest,
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("leases.edit")),
):
    from app.business_workflows.owner_ledger.owner_settlement_service import OwnerLedgerSettlementService

    result = OwnerLedgerSettlementService(db).settle_and_record(
        lease_id, installment_id, payload.account_id, payload.transaction_date, actor_id=current_user.id,
        payment_method=payload.payment_method, reference_number=payload.reference_number,
    )
    db.commit()
    return {
        "message": result["settlement_result"].message + " Owner Ledger updated.",
        "ledger_entry_id": result["ledger_entry"].id,
        "receipt_id": result["receipt_id"],
    }
