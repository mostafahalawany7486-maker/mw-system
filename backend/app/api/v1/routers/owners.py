from math import ceil
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.schemas.owner import (
    OwnerCreate, OwnerUpdate, OwnerListItemOut, OwnerDetailOut, OwnerDashboardOut,
    OwnerAddressCreate, OwnerAddressUpdate, OwnerAddressOut,
    OwnerBankAccountCreate, OwnerBankAccountUpdate, OwnerBankAccountOut,
    OwnerContactCreate, OwnerContactUpdate, OwnerContactOut,
    OwnerDocumentOut, OwnerDocumentUpdate,
)
from app.services.owner_service import OwnerService
from app.models.user import User

router = APIRouter(prefix="/owners", tags=["Property Owners"])


def _paginated(items, total, params: PaginationParams):
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


# ---------------- Dashboard ----------------
@router.get("/dashboard/summary", response_model=OwnerDashboardOut)
def owner_dashboard(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.view"))):
    return OwnerService(db).dashboard()


# ---------------- Owner CRUD ----------------
@router.get("", response_model=PaginatedResponse[OwnerListItemOut])
def list_owners(
    params: PaginationParams = Depends(get_pagination_params),
    owner_type: Optional[str] = Query(None, pattern="^(individual|company)$"),
    status: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("owners.view")),
):
    items, total = OwnerService(db).list_owners(params, owner_type, status, branch_id)
    return _paginated(items, total, params)


@router.post("", response_model=OwnerDetailOut, status_code=201)
def create_owner(payload: OwnerCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.create"))):
    return OwnerService(db).create_owner(payload.model_dump(), actor_id=current_user.id)


@router.get("/{owner_id}", response_model=OwnerDetailOut)
def get_owner(owner_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.view"))):
    return OwnerService(db).get_owner(owner_id)


@router.put("/{owner_id}", response_model=OwnerDetailOut)
def update_owner(owner_id: int, payload: OwnerUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).update_owner(owner_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{owner_id}", response_model=MessageResponse)
def delete_owner(owner_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.delete"))):
    OwnerService(db).delete_owner(owner_id, actor_id=current_user.id)
    return {"message": "Owner deleted successfully"}


# ---------------- Addresses ----------------
@router.post("/{owner_id}/addresses", response_model=OwnerAddressOut, status_code=201)
def add_address(owner_id: int, payload: OwnerAddressCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).add_address(owner_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{owner_id}/addresses/{address_id}", response_model=OwnerAddressOut)
def update_address(owner_id: int, address_id: int, payload: OwnerAddressUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).update_address(owner_id, address_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{owner_id}/addresses/{address_id}", response_model=MessageResponse)
def delete_address(owner_id: int, address_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    OwnerService(db).delete_address(owner_id, address_id, actor_id=current_user.id)
    return {"message": "Address deleted successfully"}


# ---------------- Bank Accounts ----------------
@router.post("/{owner_id}/bank-accounts", response_model=OwnerBankAccountOut, status_code=201)
def add_bank_account(owner_id: int, payload: OwnerBankAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).add_bank_account(owner_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{owner_id}/bank-accounts/{account_id}", response_model=OwnerBankAccountOut)
def update_bank_account(owner_id: int, account_id: int, payload: OwnerBankAccountUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).update_bank_account(owner_id, account_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{owner_id}/bank-accounts/{account_id}", response_model=MessageResponse)
def delete_bank_account(owner_id: int, account_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    OwnerService(db).delete_bank_account(owner_id, account_id, actor_id=current_user.id)
    return {"message": "Bank account deleted successfully"}


# ---------------- Contacts ----------------
@router.post("/{owner_id}/contacts", response_model=OwnerContactOut, status_code=201)
def add_contact(owner_id: int, payload: OwnerContactCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).add_contact(owner_id, payload.model_dump(), actor_id=current_user.id)


@router.put("/{owner_id}/contacts/{contact_id}", response_model=OwnerContactOut)
def update_contact(owner_id: int, contact_id: int, payload: OwnerContactUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).update_contact(owner_id, contact_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{owner_id}/contacts/{contact_id}", response_model=MessageResponse)
def delete_contact(owner_id: int, contact_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    OwnerService(db).delete_contact(owner_id, contact_id, actor_id=current_user.id)
    return {"message": "Contact deleted successfully"}


# ---------------- Documents ----------------
@router.post("/{owner_id}/documents", response_model=OwnerDocumentOut, status_code=201)
def upload_document(
    owner_id: int,
    document_type: str = Form(...),
    document_number: Optional[str] = Form(None),
    issue_date: Optional[date] = Form(None),
    expiry_date: Optional[date] = Form(None),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("owners.edit")),
):
    return OwnerService(db).upload_document(
        owner_id, file, document_type, document_number, issue_date, expiry_date, description, actor_id=current_user.id
    )


@router.put("/{owner_id}/documents/{document_id}", response_model=OwnerDocumentOut)
def update_document(owner_id: int, document_id: int, payload: OwnerDocumentUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    return OwnerService(db).update_document(owner_id, document_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.delete("/{owner_id}/documents/{document_id}", response_model=MessageResponse)
def delete_document(owner_id: int, document_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("owners.edit"))):
    OwnerService(db).delete_document(owner_id, document_id, actor_id=current_user.id)
    return {"message": "Document deleted successfully"}
