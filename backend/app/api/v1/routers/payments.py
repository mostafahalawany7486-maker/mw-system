"""
Payment & Collection Engine API router. Thin — every endpoint delegates
straight to PaymentWorkflowService, exactly like every other router in
this codebase delegates to its module's Service class.

Permission mapping (matches the existing 'module.action' convention in
seed.py): payments.view for reads, payments.create for capturing a new
payment, payments.edit for every lifecycle transition
(verify/cancel/refund/reverse) — mirrors how leases.py already gates
activate/terminate/renew all under a single leases.edit rather than one
permission per transition.
"""
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse
from app.schemas.payment import (
    PaymentCreate, VerifyPaymentRequest, RefundPaymentRequest, ReversePaymentRequest, CancelPaymentRequest,
    PaymentOut, CollectionDashboardOut,
)
from app.business_workflows.payment.payment_workflow_service import PaymentWorkflowService
from app.models.user import User

router = APIRouter(prefix="/payments", tags=["Payment & Collection Engine"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard ----------------
@router.get("/dashboard/summary", response_model=CollectionDashboardOut)
def collection_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.view"))):
    return PaymentWorkflowService(db).dashboard()


# ---------------- CRUD ----------------
@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.create"))):
    data = payload.model_dump()
    data["allocations"] = [a.model_dump() for a in payload.allocations]
    return PaymentWorkflowService(db).create_payment(data, actor_id=current_user.id)


@router.get("", response_model=PaginatedResponse[PaymentOut])
def list_payments(
    params: PaginationParams = Depends(get_pagination_params),
    tenant_id: Optional[int] = Query(None),
    payment_status: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("payments.view")),
):
    from datetime import date as _date
    df = _date.fromisoformat(date_from) if date_from else None
    dt = _date.fromisoformat(date_to) if date_to else None
    items, total = PaymentWorkflowService(db).list_payments(params, tenant_id, payment_status, payment_method, df, dt, search)
    return _paginated(items, total, params)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.view"))):
    return PaymentWorkflowService(db).get_payment(payment_id)


# ---------------- Lifecycle transitions ----------------
@router.post("/{payment_id}/verify", response_model=PaymentOut)
def verify_payment(payment_id: int, payload: VerifyPaymentRequest = VerifyPaymentRequest(), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.edit"))):
    return PaymentWorkflowService(db).verify_payment(payment_id, actor_id=current_user.id)


@router.post("/{payment_id}/cancel", response_model=PaymentOut)
def cancel_payment(payment_id: int, payload: CancelPaymentRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.edit"))):
    return PaymentWorkflowService(db).cancel_payment(payment_id, payload.reason, actor_id=current_user.id)


@router.post("/{payment_id}/refund", response_model=PaymentOut)
def refund_payment(payment_id: int, payload: RefundPaymentRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.edit"))):
    return PaymentWorkflowService(db).refund_payment(payment_id, payload.reason, actor_id=current_user.id, amount=payload.amount)


@router.post("/{payment_id}/reverse", response_model=PaymentOut)
def reverse_payment(payment_id: int, payload: ReversePaymentRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("payments.edit"))):
    return PaymentWorkflowService(db).reverse_payment(payment_id, payload.reason, actor_id=current_user.id)
