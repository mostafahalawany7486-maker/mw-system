from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator
from app.schemas.common import AuditFieldsOut


# ---------- Permission ----------
class PermissionOut(AuditFieldsOut):
    code: str
    module: str
    action: str
    description: Optional[str] = None


# ---------- Role ----------
class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permission_ids: List[int] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None
    status: Optional[str] = None


class RoleOut(AuditFieldsOut):
    name: str
    description: Optional[str] = None
    is_system_role: bool
    permissions: List[PermissionOut] = []


# ---------- User ----------
class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str
    role_id: Optional[int] = None
    branch_id: Optional[int] = None
    is_active: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    role_id: Optional[int] = None
    branch_id: Optional[int] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None
    avatar_url: Optional[str] = None


class UserOut(AuditFieldsOut):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_superuser: bool
    avatar_url: Optional[str] = None
    role_id: Optional[int] = None
    branch_id: Optional[int] = None
    role: Optional[RoleOut] = None


class UserMeOut(UserOut):
    permissions: List[str] = []
