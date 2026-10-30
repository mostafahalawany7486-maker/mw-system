from math import ceil
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.property import (
    PropertyCreate, PropertyUpdate, PropertyListItemOut, PropertyDetailOut, PropertyDashboardOut,
    AmenityCreate, AmenityUpdate, AmenityOut,
    PropertyImageUpdate, PropertyImageOut, PropertyDocumentUpdate, PropertyDocumentOut,
    FloorCreate, FloorUpdate, FloorOut, BuildingSummaryOut,
    BulkGenerateUnitsRequest, BulkGenerateUnitsResultOut,
)
from app.schemas.rental import RentalContractListItemOut
from app.schemas.tenant import TenantListItemOut
from app.schemas.maintenance import MaintenanceRequestListItemOut
from app.schemas.reports import ExpenseReportOut, PropertyProfitAndLossOut, PropertyFinancialDashboardOut
from app.schemas.accounting import IncomeStatementOut, PropertyCashFlowOut, PropertyLedgerOut, PropertyBalanceSummaryOut
from app.services.property_service import PropertyService, AmenityService, FloorService
from app.services.reports_service import ReportsService
from app.services.accounting_service import AccountingReportService
from app.models.user import User

router = APIRouter(tags=["Property Management"])
properties_router = APIRouter(prefix="/properties", tags=["Property Management"])
amenities_router = APIRouter(prefix="/amenities", tags=["Amenities"])
floors_router = APIRouter(prefix="/floors", tags=["Floors"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard ----------------
@properties_router.get("/dashboard/summary", response_model=PropertyDashboardOut)
def property_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    return PropertyService(db).dashboard()


# ---------------- Property CRUD ----------------
@properties_router.get("", response_model=PaginatedResponse[PropertyListItemOut])
def list_properties(
    params: PaginationParams = Depends(get_pagination_params),
    property_type: Optional[str] = Query(None),
    availability_status: Optional[str] = Query(None),
    owner_id: Optional[int] = Query(None),
    branch_id: Optional[int] = Query(None),
    city_id: Optional[int] = Query(None),
    parent_property_id: Optional[int] = Query(None),
    floor_id: Optional[int] = Query(None, description="Filter units to a specific Floor (Phase 2.0 Floor filter)"),
    include_archived: bool = Query(False, description="Include properties archived via POST /properties/{id}/archive (excluded by default)"),
    top_level_only: bool = Query(False, description="Only return Buildings/Villas/standalone properties, excluding child Units (Cascading Property Selector)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("properties.view")),
):
    items, total = PropertyService(db).list_properties(
        params, property_type, availability_status, owner_id, branch_id, city_id, parent_property_id, floor_id, include_archived, top_level_only
    )
    return _paginated(items, total, params)


@properties_router.post("", response_model=PropertyDetailOut, status_code=201)
def create_property(payload: PropertyCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.create"))):
    return PropertyService(db).create_property(payload.model_dump(), actor_id=current_user.id)


# ---------------- Bulk vacant unit pricing ----------------
# Registered before "/{property_id}" below on purpose — FastAPI matches
# routes in registration order, and "vacant-missing-price" would
# otherwise get swallowed by "/{property_id}" trying (and failing) to
# parse it as an integer id.
@properties_router.get("/vacant-missing-price")
def get_vacant_missing_price(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    """Backing list for the "Set Vacant Unit Prices" bulk screen — every
    vacant unit with no rent_price set, the same set the Dashboard's
    Vacant Units Value card already flags but can't include in its total."""
    return PropertyService(db).list_vacant_missing_price()


@properties_router.post("/vacant-missing-price/bulk-set")
def bulk_set_vacant_prices(payload: list[dict], db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    updated = PropertyService(db).bulk_set_rent_prices(payload, actor_id=current_user.id)
    return {"message": f"{updated} unit(s) updated", "updated": updated}


@properties_router.get("/{property_id}", response_model=PropertyDetailOut)
def get_property(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    return PropertyService(db).get_property(property_id)


# ---------------- Property Hub Summary (read-only) ----------------
# "Everything about this property, on one screen" — composes existing
# Occupancy/Financial/Maintenance/Owner Ledger services; see
# app/business_workflows/property_hub_service.py for the full breakdown.
@properties_router.get("/{property_id}/hub-summary")
def get_property_hub_summary(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    from app.business_workflows.property_hub_service import PropertyHubService
    return PropertyHubService(db).get_summary(property_id)


@properties_router.get("/{property_id}/units", response_model=list[PropertyListItemOut])
def list_units(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    """Child units within a Building (or any parent property)."""
    return PropertyService(db).list_units(property_id)


# ---------------- Building Management ----------------
# A Property with property_type="building" already IS the Building entity
# (Phase 4/5). These endpoints aggregate its existing Units, Floors,
# Rental Contracts, Tenants, and Maintenance Requests — reusing the same
# tables and list schemas as the Rentals/Tenants/Maintenance modules,
# scoped to the building and everything nested under it.
@properties_router.get("/{building_id}/building-summary", response_model=BuildingSummaryOut)
def building_summary(building_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    return PropertyService(db).get_building_summary(building_id)


@properties_router.get("/{building_id}/leases", response_model=PaginatedResponse[RentalContractListItemOut])
def building_leases(
    building_id: int, contract_status: Optional[str] = Query(None),
    params: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view")),
):
    items, total = PropertyService(db).get_building_leases(building_id, contract_status, params)
    return _paginated(items, total, params)


@properties_router.get("/{building_id}/tenants", response_model=list[TenantListItemOut])
def building_tenants(building_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    return PropertyService(db).get_building_tenants(building_id)


@properties_router.get("/{building_id}/maintenance-requests", response_model=PaginatedResponse[MaintenanceRequestListItemOut])
def building_maintenance_requests(
    building_id: int, params: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view")),
):
    items, total = PropertyService(db).get_building_maintenance_requests(building_id, params)
    return _paginated(items, total, params)


# ---------------- Property Profit Center ----------------
# Every Property is already a financial profit center: Transactions,
# Invoices, Journal Entry lines, and Maintenance costs all resolve to a
# property_id (see Phase 8/9/10 models, extended additively here). These
# endpoints reuse Phase 10's AccountingReportService (GL-grade: cash
# flow, income statement, ledger, balance summary — gated by the same
# `accounting.view` permission as their portfolio-wide counterparts) and
# Phase 11's ReportsService (operational: P&L, expense, financial
# dashboard — gated by `reports.view`, same as their portfolio-wide
# counterparts) rather than introducing a parallel reporting system.
@properties_router.get("/{property_id}/reports/profit-loss", response_model=PropertyProfitAndLossOut)
def property_profit_and_loss(
    property_id: int, date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).property_profit_and_loss(property_id, date_from, date_to)


@properties_router.get("/{property_id}/reports/expense", response_model=ExpenseReportOut)
def property_expense_report(
    property_id: int, date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view")),
):
    return ReportsService(db).expense_report(date_from, date_to, property_id)


@properties_router.get("/{property_id}/financial-dashboard", response_model=PropertyFinancialDashboardOut)
def property_financial_dashboard(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("reports.view"))):
    return ReportsService(db).property_financial_dashboard(property_id)


@properties_router.get("/{property_id}/reports/cash-flow", response_model=PropertyCashFlowOut)
def property_cash_flow(
    property_id: int, date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).property_cash_flow(property_id, date_from, date_to)


@properties_router.get("/{property_id}/reports/income-statement", response_model=IncomeStatementOut)
def property_income_statement(
    property_id: int, date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).income_statement(date_from, date_to, property_id)


@properties_router.get("/{property_id}/reports/ledger", response_model=PropertyLedgerOut)
def property_ledger(
    property_id: int, date_from: Optional[date] = Query(None), date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).property_ledger(property_id, date_from, date_to)


@properties_router.get("/{property_id}/reports/balance-summary", response_model=PropertyBalanceSummaryOut)
def property_balance_summary(
    property_id: int, as_of_date: date = Query(...),
    db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("accounting.view")),
):
    return AccountingReportService(db).property_balance_summary(property_id, as_of_date)


# ---------------- Floors ----------------
@properties_router.get("/{building_id}/floors", response_model=list[FloorOut])
def list_floors(building_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    return FloorService(db).list_for_building(building_id)


@properties_router.post("/{building_id}/floors", response_model=FloorOut, status_code=201)
def create_floor(building_id: int, payload: FloorCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return FloorService(db).create(building_id, payload.model_dump(), actor_id=current_user.id)


@properties_router.post("/{building_id}/bulk-generate-units", response_model=BulkGenerateUnitsResultOut, status_code=201)
def bulk_generate_units(building_id: int, payload: BulkGenerateUnitsRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return PropertyService(db).bulk_generate_units(building_id, payload.model_dump(), actor_id=current_user.id)


@floors_router.put("/{floor_id}", response_model=FloorOut)
def update_floor(floor_id: int, payload: FloorUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return FloorService(db).update(floor_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@floors_router.post("/{floor_id}/whole-floor-unit", response_model=PropertyListItemOut)
def get_or_create_whole_floor_unit(floor_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    """Backing endpoint for the "whole floor" rental contract option
    confirmed directly — get-or-creates the single Property row
    (property_type=FLOOR) that a RentalContract can point at to mean
    "this tenant rents the entire floor," instead of one specific
    unit. See PropertyService.get_or_create_floor_unit()."""
    return PropertyService(db).get_or_create_floor_unit(floor_id, actor_id=current_user.id)


@floors_router.delete("/{floor_id}", response_model=MessageResponse)
def delete_floor(floor_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    FloorService(db).delete(floor_id, actor_id=current_user.id)
    return {"message": "Floor deleted successfully"}


@properties_router.put("/{property_id}", response_model=PropertyDetailOut)
def update_property(property_id: int, payload: PropertyUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return PropertyService(db).update_property(property_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@properties_router.delete("/{property_id}", response_model=MessageResponse)
def delete_property(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.delete"))):
    PropertyService(db).delete_property(property_id, actor_id=current_user.id)
    return {"message": "Property deleted successfully"}


# ---------------- Archive (distinct from delete — see BaseRepository.archive()) ----------------
@properties_router.post("/{property_id}/archive", response_model=PropertyDetailOut)
def archive_property(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return PropertyService(db).archive_property(property_id, actor_id=current_user.id)


@properties_router.post("/{property_id}/unarchive", response_model=PropertyDetailOut)
def unarchive_property(property_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return PropertyService(db).unarchive_property(property_id, actor_id=current_user.id)


# ---------------- Images ----------------
@properties_router.post("/{property_id}/images", response_model=PropertyImageOut, status_code=201)
def upload_image(
    property_id: int,
    caption: Optional[str] = Form(None),
    is_cover: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("properties.edit")),
):
    return PropertyService(db).upload_image(property_id, file, caption, is_cover, actor_id=current_user.id)


@properties_router.put("/{property_id}/images/{image_id}", response_model=PropertyImageOut)
def update_image(property_id: int, image_id: int, payload: PropertyImageUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return PropertyService(db).update_image(property_id, image_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@properties_router.delete("/{property_id}/images/{image_id}", response_model=MessageResponse)
def delete_image(property_id: int, image_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    PropertyService(db).delete_image(property_id, image_id, actor_id=current_user.id)
    return {"message": "Image deleted successfully"}


# ---------------- Documents ----------------
@properties_router.post("/{property_id}/documents", response_model=PropertyDocumentOut, status_code=201)
def upload_document(
    property_id: int,
    document_type: str = Form(...),
    document_number: Optional[str] = Form(None),
    issue_date: Optional[date] = Form(None),
    expiry_date: Optional[date] = Form(None),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("properties.edit")),
):
    return PropertyService(db).upload_document(
        property_id, file, document_type, document_number, issue_date, expiry_date, description, actor_id=current_user.id
    )


@properties_router.put("/{property_id}/documents/{document_id}", response_model=PropertyDocumentOut)
def update_document(property_id: int, document_id: int, payload: PropertyDocumentUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return PropertyService(db).update_document(property_id, document_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@properties_router.delete("/{property_id}/documents/{document_id}", response_model=MessageResponse)
def delete_document(property_id: int, document_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    PropertyService(db).delete_document(property_id, document_id, actor_id=current_user.id)
    return {"message": "Document deleted successfully"}


# ---------------- Amenities (lookup, managed under properties.* permissions) ----------------
@amenities_router.get("", response_model=PaginatedResponse[AmenityOut])
def list_amenities(params: PaginationParams = Depends(get_pagination_params), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.view"))):
    items, total = AmenityService(db).list(params)
    return _paginated(items, total, params)


@amenities_router.post("", response_model=AmenityOut, status_code=201)
def create_amenity(payload: AmenityCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return AmenityService(db).create(payload.name, payload.category, actor_id=current_user.id)


@amenities_router.put("/{amenity_id}", response_model=AmenityOut)
def update_amenity(amenity_id: int, payload: AmenityUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    return AmenityService(db).update(amenity_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@amenities_router.delete("/{amenity_id}", response_model=MessageResponse)
def delete_amenity(amenity_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("properties.edit"))):
    AmenityService(db).delete(amenity_id, actor_id=current_user.id)
    return {"message": "Amenity deleted successfully"}


router.include_router(properties_router)
router.include_router(amenities_router)
router.include_router(floors_router)
