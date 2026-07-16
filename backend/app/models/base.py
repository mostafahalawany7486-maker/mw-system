"""
BaseModel mixin: every table in the system inherits this, guaranteeing the
mandatory columns defined in the project's database standards:
id, uuid, created_at, updated_at, deleted_at, created_by, updated_by, status.
"""
import uuid as uuid_lib
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, declared_attr
from app.core.database import Base


class RecordStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    PENDING = "pending"


class BaseModel(Base):
    """Abstract base providing standard audit/soft-delete columns."""
    __abstract__ = True

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid_lib.uuid4()), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=RecordStatus.ACTIVE, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @declared_attr
    def created_by(cls) -> Mapped[int | None]:
        return mapped_column(Integer, ForeignKey("users.id", use_alter=True), nullable=True)

    @declared_attr
    def updated_by(cls) -> Mapped[int | None]:
        return mapped_column(Integer, ForeignKey("users.id", use_alter=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
