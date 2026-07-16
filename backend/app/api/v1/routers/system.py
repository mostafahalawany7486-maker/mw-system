from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, PermissionChecker
from app.schemas.system import (
    AttachmentOut, NoteCreate, NoteUpdate, NoteOut, ActivityLogOut, AuditLogOut, NotificationOut,
)
from app.schemas.common import MessageResponse
from app.services.misc_services import AttachmentService, NoteService
from app.services.notification_service import NotificationService
from app.repositories.system_repository import ActivityLogRepository, AuditLogRepository
from app.models.user import User

router = APIRouter(tags=["Attachments, Notes, History & Notifications"])


# ---------------- Attachments ----------------
@router.post("/attachments", response_model=AttachmentOut, status_code=201)
def upload_attachment(
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AttachmentService(db).upload(file, entity_type, entity_id, description, actor_id=current_user.id)


@router.get("/attachments", response_model=list[AttachmentOut])
def list_attachments(entity_type: str = Query(...), entity_id: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return AttachmentService(db).list_for_entity(entity_type, entity_id)


@router.delete("/attachments/{attachment_id}", response_model=MessageResponse)
def delete_attachment(attachment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    AttachmentService(db).delete(attachment_id, actor_id=current_user.id)
    return {"message": "Attachment deleted successfully"}


# ---------------- Notes ----------------
@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return NoteService(db).create(payload.entity_type, payload.entity_id, payload.content, payload.is_pinned, actor_id=current_user.id)


@router.get("/notes", response_model=list[NoteOut])
def list_notes(entity_type: str = Query(...), entity_id: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return NoteService(db).list_for_entity(entity_type, entity_id)


@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return NoteService(db).update(note_id, payload.content, payload.is_pinned, actor_id=current_user.id)


@router.delete("/notes/{note_id}", response_model=MessageResponse)
def delete_note(note_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    NoteService(db).delete(note_id, actor_id=current_user.id)
    return {"message": "Note deleted successfully"}


# ---------------- Activity Log ----------------
@router.get("/activity-logs", response_model=list[ActivityLogOut])
def list_activity_logs(entity_type: str = Query(...), entity_id: int = Query(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return ActivityLogRepository(db).list_for_entity(entity_type, entity_id)


# ---------------- Audit Log (restricted) ----------------
@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("audit.view")),
):
    items, _ = AuditLogRepository(db).list(page=page, page_size=page_size, sort_by="created_at", sort_dir="desc")
    return items


# ---------------- Notifications ----------------
@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(unread_only: bool = Query(False), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return NotificationService(db).list_for_user(current_user.id, unread_only)


@router.get("/notifications/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"unread_count": NotificationService(db).unread_count(current_user.id)}


@router.post("/notifications/{notification_id}/read", response_model=MessageResponse)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = NotificationService(db)
    notif = service.repo.get(notification_id)
    if notif and notif.recipient_id == current_user.id:
        service.mark_read(notif)
        db.commit()
    return {"message": "Notification marked as read"}


@router.post("/notifications/read-all", response_model=MessageResponse)
def mark_all_notifications_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = NotificationService(db).mark_all_read(current_user.id)
    db.commit()
    return {"message": f"{count} notification(s) marked as read"}
