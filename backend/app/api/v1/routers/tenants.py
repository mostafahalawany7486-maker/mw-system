from math import ceil
from datetime import date
from typing import Optional
from io import BytesIO
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.tenant import (
    TenantCreate, TenantUpdate, TenantListItemOut, TenantDetailOut, TenantDashboardOut,
    TenantContactCreate, TenantContactUpdate, TenantContactOut,
    TenantEmergencyContactCreate, TenantEmergencyContactUpdate, TenantEmergencyContactOut,
    TenantDocumentUpdate, TenantDocumentOut,
    TenantRatingCreate, TenantRatingOut,
    BlacklistRequest,
)
from app.services.tenant_service import TenantService
from app.services.tenant_import_service import TenantImportService
from app.models.user import User

router = APIRouter(prefix="/tenants", tags=["Tenant Management"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard ----------------
@router.get("/dashboard/summary", response_model=TenantDashboardOut)
def tenant_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.view"))):
    return TenantService(db).dashboard()


# ---------------- Tenant CRUD ----------------
@router.get("", response_model=PaginatedResponse[TenantListItemOut])
def list_tenants(
    params: PaginationParams = Depends(get_pagination_params),
    tenant_type: Optional[str] = Query(None, pattern="^(individual|company)$"),
    is_blacklisted: Optional[bool] = Query(None),
    branch_id: Optional[int] = Query(None),
    building_id: Optional[int] = Query(None, description="Only tenants with an active contract under this building (direct unit, whole-floor, or whole-building)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("tenants.view")),
):
    items, total = TenantService(db).list_tenants(params, tenant_type, is_blacklisted, branch_id, building_id)
    return _paginated(items, total, params)


@router.post("", response_model=TenantDetailOut, status_code=201)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.create"))):
    return TenantService(db).create_tenant(payload.model_dump(), actor_id=current_user.id)


@router.get("/{tenant_id}", response_model=TenantDetailOut)
def get_tenant(tenant_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.view"))):
    return TenantService(db).get_tenant(tenant_id)


@router.put("/{tenant_id}", response_model=TenantDetailOut)
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).update_tenant(tenant_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{tenant_id}", response_model=MessageResponse)
def delete_tenant(tenant_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.delete"))):
    TenantService(db).delete_tenant(tenant_id, actor_id=current_user.id)
    return {"message": "Tenant deleted successfully"}


# ---------------- Blacklist ----------------
@router.post("/{tenant_id}/blacklist", response_model=TenantDetailOut)
def blacklist_tenant(tenant_id: int, payload: BlacklistRequest, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).blacklist(tenant_id, payload.reason, actor_id=current_user.id)


@router.post("/{tenant_id}/unblacklist", response_model=TenantDetailOut)
def unblacklist_tenant(tenant_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).unblacklist(tenant_id, actor_id=current_user.id)


# ---------------- Ratings ----------------
@router.post("/{tenant_id}/ratings", response_model=TenantRatingOut, status_code=201)
def add_rating(tenant_id: int, payload: TenantRatingCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).add_rating(tenant_id, payload.rating_value, payload.comment, actor_id=current_user.id)


@router.delete("/{tenant_id}/ratings/{rating_id}", response_model=MessageResponse)
def delete_rating(tenant_id: int, rating_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    TenantService(db).delete_rating(tenant_id, rating_id, actor_id=current_user.id)
    return {"message": "Rating deleted successfully"}


# ---------------- Contacts ----------------
@router.post("/{tenant_id}/contacts", response_model=TenantContactOut, status_code=201)
def add_contact(tenant_id: int, payload: TenantContactCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).add_contact(tenant_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{tenant_id}/contacts/{contact_id}", response_model=TenantContactOut)
def update_contact(tenant_id: int, contact_id: int, payload: TenantContactUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).update_contact(tenant_id, contact_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{tenant_id}/contacts/{contact_id}", response_model=MessageResponse)
def delete_contact(tenant_id: int, contact_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    TenantService(db).delete_contact(tenant_id, contact_id, actor_id=current_user.id)
    return {"message": "Contact deleted successfully"}


# ---------------- Emergency Contacts ----------------
@router.post("/{tenant_id}/emergency-contacts", response_model=TenantEmergencyContactOut, status_code=201)
def add_emergency_contact(tenant_id: int, payload: TenantEmergencyContactCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).add_emergency_contact(tenant_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{tenant_id}/emergency-contacts/{contact_id}", response_model=TenantEmergencyContactOut)
def update_emergency_contact(tenant_id: int, contact_id: int, payload: TenantEmergencyContactUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).update_emergency_contact(tenant_id, contact_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{tenant_id}/emergency-contacts/{contact_id}", response_model=MessageResponse)
def delete_emergency_contact(tenant_id: int, contact_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    TenantService(db).delete_emergency_contact(tenant_id, contact_id, actor_id=current_user.id)
    return {"message": "Emergency contact deleted successfully"}


# ---------------- Documents ----------------
@router.post("/{tenant_id}/documents", response_model=TenantDocumentOut, status_code=201)
def upload_document(
    tenant_id: int,
    document_type: str = Form(...),
    document_number: Optional[str] = Form(None),
    issue_date: Optional[date] = Form(None),
    expiry_date: Optional[date] = Form(None),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("tenants.edit")),
):
    return TenantService(db).upload_document(
        tenant_id, file, document_type, document_number, issue_date, expiry_date, description, actor_id=current_user.id
    )


@router.put("/{tenant_id}/documents/{document_id}", response_model=TenantDocumentOut)
def update_document(tenant_id: int, document_id: int, payload: TenantDocumentUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    return TenantService(db).update_document(tenant_id, document_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{tenant_id}/documents/{document_id}", response_model=MessageResponse)
def delete_document(tenant_id: int, document_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.edit"))):
    TenantService(db).delete_document(tenant_id, document_id, actor_id=current_user.id)
    return {"message": "Document deleted successfully"}


# ---------------- Bulk Tenant Import (per building) ----------------
# Two-step: download a pre-filled .xlsx template for one building's
# units, fill it in, upload it back. Reuses the existing tenants.create
# permission — no new permission module. Each row only ever creates a
# plain Tenant; linking to a specific unit's Rental Contract stays a
# separate manual step. See app/services/tenant_import_service.py for
# the full design rationale.
@router.get("/import-template/{building_id}")
def download_tenant_import_template(building_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.create"))):
    file_bytes, filename = TenantImportService(db).render_template(building_id)
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/{building_id}")
def upload_tenant_import(building_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("tenants.create"))):
    """All-or-nothing: if any row fails validation, nothing is created
    and the response lists every row's error so the whole file can be
    fixed and re-uploaded in one go."""
    return TenantImportService(db).parse_and_import(building_id, file, actor_id=current_user.id)
