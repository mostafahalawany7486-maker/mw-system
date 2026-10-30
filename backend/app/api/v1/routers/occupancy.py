"""
Occupancy & Unit Lifecycle Engine API router. Thin — every endpoint
delegates to OccupancyService (business_workflows/occupancy/).

Beyond the spec's literal 4 endpoints (GET /occupancy, GET
/occupancy/buildings, GET /occupancy/units, POST /occupancy/recalculate),
five supporting endpoints were added since six of the eleven required
statuses (Reserved, Cleaning, Inspection, Blocked, Renovation, Inactive)
and Notice Period would otherwise be permanently unreachable through
the API — see occupancy_events.py and docs/occupancy-engine.md.
"""
from typing import Optional
from math import ceil
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import PermissionChecker
from app.schemas.common import PaginatedResponse
from app.schemas.occupancy import (
    SetOverrideRequest, ClearOverrideRequest, SetNoticeRequest,
    UnitOccupancyOut, OccupancyDashboardOut, BuildingOccupancySummaryOut,
    OccupancyOverrideOut, OccupancyHistoryItemOut, RecalculateResultOut,
)
from app.business_workflows.occupancy.occupancy_service import OccupancyService
from app.models.user import User

router = APIRouter(prefix="/occupancy", tags=["Occupancy & Unit Lifecycle Engine"])


@router.get("", response_model=OccupancyDashboardOut)
def get_occupancy_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.view"))):
    return OccupancyService(db).get_dashboard()


@router.get("/buildings", response_model=list[BuildingOccupancySummaryOut])
def get_buildings_summary(
    building_id: Optional[int] = Query(None, description="Scope to a single building; omit for every building"),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.view")),
):
    return OccupancyService(db).get_buildings(building_id)


@router.get("/units", response_model=PaginatedResponse[UnitOccupancyOut])
def get_units(
    building_id: Optional[int] = Query(None),
    occupancy_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.view")),
):
    items, total = OccupancyService(db).get_units(building_id, occupancy_status, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=ceil(total / page_size) if page_size else 0)


@router.post("/recalculate", response_model=RecalculateResultOut)
def recalculate(
    building_id: Optional[int] = Query(None, description="Scope the sweep to one building; omit to sweep every unit"),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.edit")),
):
    return OccupancyService(db).recalculate(building_id, actor_id=current_user.id)


# ---------------- Overrides (make Reserved/Cleaning/Inspection/Blocked/Renovation/Inactive reachable) ----------------
@router.post("/units/{property_id}/override", response_model=OccupancyOverrideOut, status_code=201)
def set_override(property_id: int, payload: SetOverrideRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.edit"))):
    return OccupancyService(db).set_override(property_id, payload.override_status, payload.reason, payload.expires_at, actor_id=current_user.id)


@router.post("/overrides/{override_id}/clear", response_model=OccupancyOverrideOut)
def clear_override(override_id: int, payload: ClearOverrideRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.edit"))):
    return OccupancyService(db).clear_override(override_id, payload.reason, actor_id=current_user.id)


# ---------------- Notice period (make Notice Period reachable) ----------------
@router.post("/contracts/{contract_id}/notice", response_model=UnitOccupancyOut)
def set_move_out_notice(contract_id: int, payload: SetNoticeRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.edit"))):
    service = OccupancyService(db)
    contract = service.set_move_out_notice(contract_id, payload.move_out_notice_date, actor_id=current_user.id)
    status_value, reason = service.engine.compute_unit_status(contract.property_id)
    unit = service.property_repo.get(contract.property_id)
    return {
        "property_id": unit.id, "property_title": unit.title, "property_code": unit.property_code,
        "unit_number": unit.unit_number, "building_id": unit.parent_property_id,
        "building_title": unit.parent.title if unit.parent else None,
        "occupancy_status": status_value, "status_reason": reason,
        "tenant_display_name": contract.tenant_display_name, "rental_contract_id": contract.id,
        "contract_end_date": contract.end_date, "rent_amount": contract.rent_amount,
    }


# ---------------- Per-unit audit trail ----------------
@router.get("/units/{property_id}/history", response_model=list[OccupancyHistoryItemOut])
def get_unit_history(property_id: int, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("occupancy.view"))):
    return OccupancyService(db).get_unit_history(property_id, limit)
