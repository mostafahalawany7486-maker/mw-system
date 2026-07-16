from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from math import ceil

from app.core.database import get_db
from app.api.deps import get_current_user, get_pagination_params, PermissionChecker
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.schemas.common import PaginationParams, PaginatedResponse, MessageResponse
from app.services.user_service import UserService
from app.models.user import User

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=PaginatedResponse[UserOut])
def list_users(
    params: PaginationParams = Depends(get_pagination_params),
    role_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("users.view")),
):
    items, total = UserService(db).list_users(params, role_id=role_id, is_active=is_active)
    return PaginatedResponse(
        items=items, total=total, page=params.page, page_size=params.page_size,
        total_pages=ceil(total / params.page_size) if params.page_size else 0,
    )


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("users.view"))):
    return UserService(db).get_user(user_id)


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("users.create"))):
    return UserService(db).create_user(payload.model_dump(), actor_id=current_user.id)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("users.edit"))):
    return UserService(db).update_user(user_id, payload.model_dump(exclude_unset=True), actor_id=current_user.id)


@router.post("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("users.edit"))):
    return UserService(db).deactivate_user(user_id, actor_id=current_user.id)


@router.post("/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("users.edit"))):
    return UserService(db).activate_user(user_id, actor_id=current_user.id)


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(PermissionChecker("users.delete"))):
    UserService(db).soft_delete_user(user_id, actor_id=current_user.id)
    return {"message": "User deleted successfully"}
