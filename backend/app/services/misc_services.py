from typing import Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.repositories.system_repository import AttachmentRepository, NoteRepository
from app.services.file_storage_service import FileUploadService
from app.services.audit_service import AuditService
from app.models.user import User


class AttachmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AttachmentRepository(db)
        self.uploader = FileUploadService()
        self.audit = AuditService(db)

    def upload(self, file: UploadFile, entity_type: str, entity_id: int, description: Optional[str], actor_id: Optional[int]):
        meta = self.uploader.upload(file, entity_type, entity_id)
        meta["entity_type"] = entity_type
        meta["entity_id"] = entity_id
        meta["description"] = description
        attachment = self.repo.create(meta, actor_id=actor_id)
        self.audit.log_activity(entity_type, entity_id, "attachment_added", f"File '{attachment.file_name}' uploaded", actor_id)
        self.db.commit()
        return attachment

    def list_for_entity(self, entity_type: str, entity_id: int):
        return self.repo.list_for_entity(entity_type, entity_id)

    def delete(self, attachment_id: int, actor_id: Optional[int]):
        attachment = self.repo.get(attachment_id)
        if not attachment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
        self.uploader.delete(attachment.file_path)
        self.repo.soft_delete(attachment, actor_id=actor_id)
        self.audit.log_activity(attachment.entity_type, attachment.entity_id, "attachment_removed", f"File '{attachment.file_name}' removed", actor_id)
        self.db.commit()


class NoteService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NoteRepository(db)
        self.audit = AuditService(db)

    def create(self, entity_type: str, entity_id: int, content: str, is_pinned: bool, actor_id: Optional[int]):
        note = self.repo.create(
            {"entity_type": entity_type, "entity_id": entity_id, "content": content, "is_pinned": is_pinned},
            actor_id=actor_id,
        )
        self.audit.log_activity(entity_type, entity_id, "note_added", "A note was added", actor_id)
        self.db.commit()
        return note

    def list_for_entity(self, entity_type: str, entity_id: int):
        return self.repo.list_for_entity(entity_type, entity_id)

    def update(self, note_id: int, content: Optional[str], is_pinned: Optional[bool], actor_id: Optional[int]):
        note = self.repo.get(note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        data = {}
        if content is not None:
            data["content"] = content
        if is_pinned is not None:
            data["is_pinned"] = is_pinned
        self.repo.update(note, data, actor_id=actor_id)
        self.db.commit()
        return note

    def delete(self, note_id: int, actor_id: Optional[int]):
        note = self.repo.get(note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        self.repo.soft_delete(note, actor_id=actor_id)
        self.db.commit()


class DashboardService:
    """
    Phase 1 dashboard: system-level widgets (user counts, branches, recent
    activity). Business widgets (properties, leases, revenue) arrive in
    later phases once those modules exist — this service is structured so
    adding widgets later is additive, not a rewrite.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_summary(self, current_user: User) -> dict:
        from app.models.user import User as UserModel, Role
        from app.models.organization import Branch
        from app.models.system import ActivityLog, Notification
        from app.models.owner import Owner

        total_users = self.db.execute(
            select(func.count()).select_from(UserModel).where(UserModel.deleted_at.is_(None))
        ).scalar_one()
        active_users = self.db.execute(
            select(func.count()).select_from(UserModel).where(UserModel.deleted_at.is_(None), UserModel.is_active.is_(True))
        ).scalar_one()
        total_roles = self.db.execute(
            select(func.count()).select_from(Role).where(Role.deleted_at.is_(None))
        ).scalar_one()
        total_branches = self.db.execute(
            select(func.count()).select_from(Branch).where(Branch.deleted_at.is_(None))
        ).scalar_one()
        total_owners = self.db.execute(
            select(func.count()).select_from(Owner).where(Owner.deleted_at.is_(None))
        ).scalar_one()
        recent_activity = self.db.execute(
            select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(10)
        ).scalars().all()
        unread_notifications = self.db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_id == current_user.id, Notification.is_read.is_(False)
            )
        ).scalar_one()

        return {
            "widgets": {
                "total_users": total_users,
                "active_users": active_users,
                "total_roles": total_roles,
                "total_branches": total_branches,
                "total_owners": total_owners,
                "unread_notifications": unread_notifications,
            },
            "recent_activity": [
                {
                    "action": a.action,
                    "description": a.description,
                    "entity_type": a.entity_type,
                    "entity_id": a.entity_id,
                    "created_at": a.created_at.isoformat(),
                }
                for a in recent_activity
            ],
        }
