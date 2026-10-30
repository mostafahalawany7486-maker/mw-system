from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.user_repository import RoleRepository, PermissionRepository
from app.models.user import Role
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService


class RoleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RoleRepository(db)
        self.perm_repo = PermissionRepository(db)
        self.audit = AuditService(db)

    def list_roles(self, params: PaginationParams):
        return self.repo.list(
            page=params.page, page_size=params.page_size, search=params.search,
            search_fields=["name", "description"], sort_by=params.sort_by, sort_dir=params.sort_dir,
        )

    def get_role(self, role_id: int) -> Role:
        role = self.repo.get_with_permissions(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return role

    def create_role(self, name: str, description: Optional[str], permission_ids: list[int], actor_id: Optional[int]) -> Role:
        if self.repo.get_by_name(name):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A role with this name already exists")
        role = self.repo.create({"name": name, "description": description}, actor_id=actor_id)
        role.permissions = self.perm_repo.get_by_ids(permission_ids)
        self.audit.log_activity("role", role.id, "created", f"Role '{role.name}' created", actor_id)
        self.db.commit()
        return self.repo.get_with_permissions(role.id)

    def update_role(self, role_id: int, name, description, permission_ids: Optional[list[int]], status_: Optional[str], actor_id: Optional[int]) -> Role:
        role = self.get_role(role_id)
        if role.is_system_role and (name or status_):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Built-in system roles cannot be renamed or disabled")
        if name:
            role.name = name
        if description is not None:
            role.description = description
        if status_:
            role.status = status_
        if permission_ids is not None:
            role.permissions = self.perm_repo.get_by_ids(permission_ids)
        self.audit.log_activity("role", role.id, "updated", f"Role '{role.name}' updated", actor_id)
        self.db.commit()
        return self.repo.get_with_permissions(role.id)

    def delete_role(self, role_id: int, actor_id: Optional[int]) -> None:
        role = self.get_role(role_id)
        if role.is_system_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Built-in system roles cannot be deleted")
        if role.users:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a role that is assigned to users")
        self.repo.soft_delete(role, actor_id=actor_id)
        self.audit.log_activity("role", role.id, "deleted", f"Role '{role.name}' deleted", actor_id)
        self.db.commit()

    def list_permissions(self):
        items, total = self.perm_repo.list(page=1, page_size=1000, sort_by="module")
        return items
