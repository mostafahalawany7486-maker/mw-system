from typing import Optional, Any
from pydantic import BaseModel
from app.schemas.common import AuditFieldsOut


class AttachmentOut(AuditFieldsOut):
    entity_type: str
    entity_id: int
    file_name: str
    file_url: Optional[str] = None
    file_size_bytes: int
    mime_type: str
    description: Optional[str] = None


class NoteCreate(BaseModel):
    entity_type: str
    entity_id: int
    content: str
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    is_pinned: Optional[bool] = None


class NoteOut(AuditFieldsOut):
    entity_type: str
    entity_id: int
    content: str
    is_pinned: bool


class ActivityLogOut(AuditFieldsOut):
    entity_type: str
    entity_id: int
    action: str
    description: str
    actor_id: Optional[int] = None


class AuditLogOut(AuditFieldsOut):
    entity_type: str
    entity_id: int
    action: str
    changed_fields: Optional[dict[str, Any]] = None
    actor_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class NotificationOut(AuditFieldsOut):
    recipient_id: int
    title: str
    message: str
    notification_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    is_read: bool
