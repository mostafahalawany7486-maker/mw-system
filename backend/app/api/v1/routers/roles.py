from math import ceil
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_pagination_params, PermissionChecker
from app.schemas.user import RoleCreate, RoleUpdate, RoleOut, PermissionOut
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.services.role_service import RoleService
from app.models.user import User

router = APIRouter(prefix="/roles", tags=["Roles & Permissions"])


@router.get("", response_model=PaginatedResponse[RoleOut])
def list_roles(
    params: PaginationParams = Depends(get_pagination_params),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("roles.view")),
):
    items, total = RoleService(db).list_roles(params)
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("roles.view"))):
    return RoleService(db).list_permissions()


@router.get("/{role_id}", response_model=RoleOut)
def get_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("roles.view"))):
    return RoleService(db).get_role(role_id)


@router.post("", response_model=RoleOut, status_code=201)
def create_role(payload: RoleCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("roles.create"))):
    return RoleService(db).create_role(payload.name, payload.description, payload.permission_ids, actor_id=current_user.id)


@router.put("/{role_id}", response_model=RoleOut)
def update_role(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("roles.edit"))):
    return RoleService(db).update_role(
        role_id, payload.name, payload.description, payload.permission_ids, payload.status, actor_id=current_user.id
    )


@router.delete("/{role_id}", response_model=MessageResponse)
def delete_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("roles.delete"))):
    RoleService(db).delete_role(role_id, actor_id=current_user.id)
    return {"message": "Role deleted successfully"}
