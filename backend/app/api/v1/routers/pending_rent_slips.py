from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.pending_rent_slip import (
    GeneratePendingSlipsRequest, ConfirmCollectionRequest, BulkSlipIdsRequest,
    PendingRentSlipListItemOut, PendingRentSlipDashboardOut,
)
from app.services.pending_rent_slip_service import PendingRentSlipService
from app.models.user import User

router = APIRouter(prefix="/pending-rent-slips", tags=["Pending Rent Slips"])


def _paginated(items, total, params: PaginationParams):
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size, "total_pages": max(1, (total + params.page_size - 1) // params.page_size)}


@router.get("/dashboard/summary", response_model=PendingRentSlipDashboardOut)
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    return PendingRentSlipService(db).dashboard()


@router.get("", response_model=PaginatedResponse[PendingRentSlipListItemOut])
def list_slips(
    params: PaginationParams = Depends(get_pagination_params),
    rental_month: Optional[str] = Query(None, description="YYYY-MM-DD (first of month)"),
    slip_status: Optional[str] = Query(None),
    property_id: Optional[int] = Query(None),
    building_id: Optional[int] = Query(None, description="Matches the building itself or any of its child units"),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("rent_vouchers.view")),
):
    parsed_month = date.fromisoformat(rental_month) if rental_month else None
    items, total = PendingRentSlipService(db).list_slips(params, parsed_month, slip_status, property_id, building_id)
    return _paginated(items, total, params)


@router.post("/generate")
def generate_slips(payload: GeneratePendingSlipsRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.create"))):
    result = PendingRentSlipService(db).generate_slips(
        payload.rental_month, [e.model_dump() for e in payload.entries], actor_id=current_user.id,
    )
    return {
        "created_count": result["created_count"],
        "already_existed_count": result["already_existed_count"],
        "slips": [PendingRentSlipListItemOut.model_validate(s, from_attributes=True) for s in result["slips"]],
    }


@router.get("/{slip_id}", response_model=PendingRentSlipListItemOut)
def get_slip(slip_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    return PendingRentSlipService(db).get_slip(slip_id)


@router.post("/{slip_id}/cancel", response_model=PendingRentSlipListItemOut)
def cancel_slip(slip_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.edit"))):
    return PendingRentSlipService(db).cancel_slip(slip_id, actor_id=current_user.id)


# ---------------- Printing (never creates a Transaction or RentVoucher) ----------------
@router.post("/print-data/bulk")
def get_bulk_print_data(payload: BulkSlipIdsRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    return PendingRentSlipService(db).get_bulk_print_data(payload.slip_ids)


@router.post("/{slip_id}/record-print", response_model=MessageResponse)
def record_print(slip_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    PendingRentSlipService(db).record_print(slip_id, actor_id=current_user.id)
    return {"message": "Print recorded"}


# ---------------- Confirm collection — the only endpoint that creates a
# real Transaction + real RentVoucher pair, via the existing unmodified
# services. Reuses payments/financial-level create permission, since
# this is functionally "record a payment," not a rent-voucher action. ----------------
@router.post("/{slip_id}/confirm-collection")
def confirm_collection(slip_id: int, payload: ConfirmCollectionRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("financial.create"))):
    return PendingRentSlipService(db).confirm_collection(
        slip_id, payload.account_id, payload.payment_method, payload.payment_date, payload.reference_number, actor_id=current_user.id,
    )
