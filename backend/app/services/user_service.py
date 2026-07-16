from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository, RoleRepository, PermissionRepository
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserRepository(db)
        self.role_repo = RoleRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    def list_users(self, params: PaginationParams, role_id: Optional[int] = None, is_active: Optional[bool] = None):
        filters = {}
        if role_id is not None:
            filters["role_id"] = role_id
        if is_active is not None:
            filters["is_active"] = is_active
        items, total = self.repo.list_with_role(
            page=params.page, page_size=params.page_size, search=params.search,
            sort_by=params.sort_by, sort_dir=params.sort_dir, filters=filters,
        )
        return items, total

    def get_user(self, user_id: int) -> User:
        user = self.repo.get_with_role(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    def create_user(self, data: dict, actor_id: Optional[int]) -> User:
        existing = self.repo.get_by_email(data["email"])
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")
        if data.get("role_id"):
            role = self.role_repo.get(data["role_id"])
            if not role:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role_id")

        payload = dict(data)
        raw_password = payload.pop("password")
        payload["email"] = payload["email"].lower()
        payload["hashed_password"] = hash_password(raw_password)

        user = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity("user", user.id, "created", f"User {user.email} created", actor_id)
        self.audit.log_audit("user", user.id, "created", {"email": {"old": None, "new": user.email}}, actor_id)
        self.db.commit()
        return self.repo.get_with_role(user.id)

    def update_user(self, user_id: int, data: dict, actor_id: Optional[int]) -> User:
        user = self.get_user(user_id)
        before = {"first_name": user.first_name, "last_name": user.last_name, "role_id": user.role_id, "is_active": user.is_active}
        self.repo.update(user, data, actor_id=actor_id)
        after = {"first_name": user.first_name, "last_name": user.last_name, "role_id": user.role_id, "is_active": user.is_active}
        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity("user", user.id, "updated", f"User {user.email} updated", actor_id)
            self.audit.log_audit("user", user.id, "updated", changes, actor_id)
        self.db.commit()
        return self.repo.get_with_role(user.id)

    def deactivate_user(self, user_id: int, actor_id: Optional[int]) -> User:
        user = self.get_user(user_id)
        user.is_active = False
        self.audit.log_activity("user", user.id, "deactivated", f"User {user.email} deactivated", actor_id)
        self.db.commit()
        return user

    def activate_user(self, user_id: int, actor_id: Optional[int]) -> User:
        user = self.get_user(user_id)
        user.is_active = True
        self.audit.log_activity("user", user.id, "activated", f"User {user.email} reactivated", actor_id)
        self.db.commit()
        return user

    def soft_delete_user(self, user_id: int, actor_id: Optional[int]) -> None:
        user = self.get_user(user_id)
        self.repo.soft_delete(user, actor_id=actor_id)
        self.audit.log_activity("user", user.id, "deleted", f"User {user.email} deleted", actor_id)
        self.db.commit()
