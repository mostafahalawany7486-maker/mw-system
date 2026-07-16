from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.system import Attachment, Note, ActivityLog, AuditLog, Notification
from app.repositories.base import BaseRepository


class AttachmentRepository(BaseRepository[Attachment]):
    def __init__(self, db: Session):
        super().__init__(Attachment, db)

    def list_for_entity(self, entity_type: str, entity_id: int) -> list[Attachment]:
        stmt = select(Attachment).where(
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
            Attachment.deleted_at.is_(None),
        ).order_by(Attachment.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())


class NoteRepository(BaseRepository[Note]):
    def __init__(self, db: Session):
        super().__init__(Note, db)

    def list_for_entity(self, entity_type: str, entity_id: int) -> list[Note]:
        stmt = select(Note).where(
            Note.entity_type == entity_type,
            Note.entity_id == entity_id,
            Note.deleted_at.is_(None),
        ).order_by(Note.is_pinned.desc(), Note.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())


class ActivityLogRepository(BaseRepository[ActivityLog]):
    def __init__(self, db: Session):
        super().__init__(ActivityLog, db)

    def list_for_entity(self, entity_type: str, entity_id: int) -> list[ActivityLog]:
        stmt = select(ActivityLog).where(
            ActivityLog.entity_type == entity_type,
            ActivityLog.entity_id == entity_id,
        ).order_by(ActivityLog.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: Session):
        super().__init__(AuditLog, db)


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: Session):
        super().__init__(Notification, db)

    def list_for_user(self, user_id: int, unread_only: bool = False) -> list[Notification]:
        stmt = select(Notification).where(Notification.recipient_id == user_id, Notification.deleted_at.is_(None))
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def unread_count(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Notification).where(
            Notification.recipient_id == user_id,
            Notification.is_read.is_(False),
            Notification.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one()
