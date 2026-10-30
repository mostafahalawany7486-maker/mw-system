"""
Rent Cycle Engine API router. Thin — every endpoint delegates straight
to RentCycleService, exactly like every other router in this codebase
delegates to its module's Service class.

Permission mapping (matches the existing 'module.action' convention in
seed.py — see MODULES list there): rent_cycles.view for reads,
rent_cycles.create for creation, rent_cycles.edit for every lifecycle
transition (generate/close/reopen/cancel). This mirrors how, e.g.,
leases.py already gates activate/terminate/renew all under a single
"leases.edit" permission rather than one permission per transition.

Regeneration (`force=true` on /generate) additionally requires the
caller to be a superuser — enforced here via `current_user.is_superuser`
before calling the service, on top of RentCycleValidator's own check,
so the 403 is raised as early as possible with a clear message.
"""
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse
from app.schemas.rent_cycle import (
    RentCycleCreate, GenerateCycleRequest, CloseCycleRequest, CancelCycleRequest,
    RentCycleListItemOut, RentCycleDetailOut, RentCycleDashboardOut, RentCycleGenerateResultOut,
)
from app.business_workflows.rent_cycle.rent_cycle_service import RentCycleService
from app.models.user import User

router = APIRouter(prefix="/rent-cycles", tags=["Rent Cycle Engine"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard ----------------
@router.get("/dashboard/summary", response_model=RentCycleDashboardOut)
def rent_cycle_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_cycles.view"))):
    return RentCycleService(db).dashboard()


# ---------------- CRUD ----------------
@router.post("", response_model=RentCycleDetailOut, status_code=201)
def create_rent_cycle(
    payload: RentCycleCreate, db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("rent_cycles.create")),
):
    return RentCycleService(db).create_cycle(payload.model_dump(), actor_id=current_user.id)


@router.get("", response_model=PaginatedResponse[RentCycleListItemOut])
def list_rent_cycles(
    params: PaginationParams = Depends(get_pagination_params),
    year: Optional[int] = Query(None),
    cycle_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("rent_cycles.view")),
):
    items, total = RentCycleService(db).list_cycles(params, year, cycle_status)
    return _paginated(items, total, params)


@router.get("/{cycle_id}", response_model=RentCycleDetailOut)
def get_rent_cycle(cycle_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_cycles.view"))):
    return RentCycleService(db).get_cycle(cycle_id)


# ---------------- Workflow transitions ----------------
@router.post("/{cycle_id}/generate", response_model=RentCycleGenerateResultOut)
def generate_rent_cycle(
    cycle_id: int, payload: GenerateCycleRequest = GenerateCycleRequest(),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_cycles.edit")),
):
    if payload.force and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Regenerating a rent cycle requires administrator approval",
        )
    cycle, result = RentCycleService(db).generate(cycle_id, actor_id=current_user.id, is_admin=current_user.is_superuser, force=payload.force)
    message = (
        f"{result.invoices_generated} invoice(s) and {result.receipts_generated} receipt(s) generated."
        if (result.invoices_generated or result.receipts_generated)
        else "No changes — this cycle was already generated (pass force=true as an administrator to regenerate)."
    )
    return RentCycleGenerateResultOut(
        cycle=RentCycleDetailOut.model_validate(cycle), invoices_generated=result.invoices_generated,
        receipts_generated=result.receipts_generated, leases_skipped=result.leases_skipped,
        message=message,
    )


@router.post("/{cycle_id}/close", response_model=RentCycleDetailOut)
def close_rent_cycle(
    cycle_id: int, payload: CloseCycleRequest = CloseCycleRequest(),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_cycles.edit")),
):
    return RentCycleService(db).close_cycle(cycle_id, payload.notes, actor_id=current_user.id)


@router.post("/{cycle_id}/reopen", response_model=RentCycleDetailOut)
def reopen_rent_cycle(cycle_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_cycles.edit"))):
    return RentCycleService(db).reopen_cycle(cycle_id, actor_id=current_user.id)


@router.post("/{cycle_id}/cancel", response_model=RentCycleDetailOut)
def cancel_rent_cycle(
    cycle_id: int, payload: CancelCycleRequest,
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_cycles.edit")),
):
    return RentCycleService(db).cancel_cycle(cycle_id, payload.reason, actor_id=current_user.id)
