"""
Rent Voucher module API router. Thin — delegates to RentVoucherService,
exactly like every other router in this codebase delegates to its
module's Service class.

Permission mapping (matches the existing 'module.action' convention,
see MODULES in seed.py): rent_vouchers.view for reads,
rent_vouchers.create for generation, rent_vouchers.edit for recording a
print/reprint — mirrors how rentals.py already gates its own
record_print endpoint under rentals.edit rather than a separate
permission.
"""
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse
from app.schemas.rent_voucher import (
    GenerateVouchersRequest, GenerateVouchersResultOut, RentVoucherOut, RentVoucherPrintDataOut,
    BulkVoucherIdsRequest,
)
from app.services.rent_voucher_service import RentVoucherService
from app.models.user import User

router = APIRouter(prefix="/rent-vouchers", tags=["Rent Voucher Module"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Generation ----------------
@router.post("/generate", response_model=GenerateVouchersResultOut, status_code=201)
def generate_vouchers(
    payload: GenerateVouchersRequest, db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("rent_vouchers.create")),
):
    vouchers, created, already_existed = RentVoucherService(db).generate_vouchers(
        payload.transaction_ids, payload.rental_month, actor_id=current_user.id, combine=payload.combine,
    )
    message = (
        f"{created} voucher(s) generated"
        + (f", {already_existed} already existed and were reused" if already_existed else "") + "."
    )
    return GenerateVouchersResultOut(vouchers=vouchers, created_count=created, already_existed_count=already_existed, message=message)


# ---------------- Lookups ----------------
@router.get("", response_model=PaginatedResponse[RentVoucherOut])
def list_vouchers(
    params: PaginationParams = Depends(get_pagination_params),
    rental_month: Optional[str] = Query(None, description="YYYY-MM-DD (first of month)"),
    copy_type: Optional[str] = Query(None),
    transaction_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("rent_vouchers.view")),
):
    from datetime import date as _date
    parsed_month = _date.fromisoformat(rental_month) if rental_month else None
    items, total = RentVoucherService(db).list_vouchers(params, parsed_month, copy_type, transaction_id)
    return _paginated(items, total, params)


@router.get("/barcode/{barcode_value}", response_model=RentVoucherOut)
def get_voucher_by_barcode(barcode_value: str, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    """Backs barcode-scan lookup — quick searching/retrieving a voucher
    by scanning it, per spec."""
    return RentVoucherService(db).get_voucher_by_barcode(barcode_value)


@router.get("/{voucher_id}", response_model=RentVoucherOut)
def get_voucher(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    return RentVoucherService(db).get_voucher(voucher_id)


@router.get("/{voucher_id}/print-data", response_model=RentVoucherPrintDataOut)
def get_voucher_print_data(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    """The bilingual print-ready DTO the frontend renders into the
    A4/four-per-page letterhead-compatible layout and sends to the
    browser's print dialog — see docs/rent-voucher-module.md."""
    return RentVoucherService(db).get_voucher_print_data(voucher_id)


@router.post("/print-data/bulk", response_model=list[RentVoucherPrintDataOut])
def get_bulk_voucher_print_data(payload: BulkVoucherIdsRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.view"))):
    """Batch variant for printing a full A4 sheet (up to four vouchers)
    in one call."""
    return RentVoucherService(db).get_bulk_print_data(payload.voucher_ids)


# ---------------- Print / reprint tracking ----------------
@router.post("/{voucher_id}/record-print", response_model=RentVoucherOut)
def record_voucher_print(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("rent_vouchers.edit"))):
    """Called by the frontend immediately before invoking the browser
    print dialog, exactly like rentals.py's own record_print endpoint."""
    return RentVoucherService(db).record_print(voucher_id, actor_id=current_user.id)
