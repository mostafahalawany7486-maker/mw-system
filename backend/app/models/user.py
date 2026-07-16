"""
RBAC core: User, Role, Permission, and the role<->permission association.
Design: a User has exactly one Role (simple, predictable RBAC for Phase 1).
A Role has many Permissions (many-to-many). Permission codes follow the
'module.action' convention, e.g. 'users.create', 'leases.approve'.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, ForeignKey, Table, Column, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, Base

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(BaseModel):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)  # e.g. users.create
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # e.g. users
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. create
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    roles: Mapped[List["Role"]] = relationship(secondary=role_permissions, back_populates="permissions")


class Role(BaseModel):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=False)  # protects built-in roles from deletion

    permissions: Mapped[List["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")
    users: Mapped[List["User"]] = relationship(back_populates="role", foreign_keys="[User.role_id]")


class User(BaseModel):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    role_id: Mapped[Optional[int]] = mapped_column(ForeignKey("roles.id"), nullable=True)
    role: Mapped[Optional["Role"]] = relationship(back_populates="users", foreign_keys=[role_id])

    branch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("branches.id"), nullable=True)

    # Password reset / security
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
