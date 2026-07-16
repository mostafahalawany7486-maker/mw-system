"""
Cross-cutting system infrastructure tables, usable by every future module:
Attachments, Notes, Activity Log, Audit Log, Notifications.
These use a generic (entity_type, entity_id) polymorphic reference so any
future entity (Property, Lease, Tenant, etc.) can attach files/notes/history
without schema changes — this is what keeps the system 'modular' per spec.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, Text, Integer, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class Attachment(BaseModel):
    __tablename__ = "attachments"

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g. "user", "property"
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # storage key/path
    file_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")  # local|azure_blob
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class Note(BaseModel):
    __tablename__ = "notes"

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)


class ActivityLog(BaseModel):
    """Human-readable timeline of business actions ('John updated Lease #102')."""
    __tablename__ = "activity_logs"

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # created|updated|deleted|status_changed...
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class AuditLog(BaseModel):
    """Machine-precise before/after field diff, for compliance/security review."""
    __tablename__ = "audit_logs"

    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"field": {"old":..,"new":..}}
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class Notification(BaseModel):
    __tablename__ = "notifications"

    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), default="info")  # info|warning|success|error
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="in_app")  # in_app|email|sms (future)
