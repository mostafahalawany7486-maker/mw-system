from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.repositories.system_repository import NotificationRepository
from app.models.system import Notification


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)

    def notify(
        self,
        recipient_id: int,
        title: str,
        message: str,
        notification_type: str = "info",
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        channel: str = "in_app",
    ) -> Notification:
        return self.repo.create({
            "recipient_id": recipient_id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "channel": channel,
        })

    def list_for_user(self, user_id: int, unread_only: bool = False) -> list[Notification]:
        return self.repo.list_for_user(user_id, unread_only)

    def unread_count(self, user_id: int) -> int:
        return self.repo.unread_count(user_id)

    def mark_read(self, notification: Notification) -> Notification:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        self.db.flush()
        return notification

    def mark_all_read(self, user_id: int) -> int:
        items = self.repo.list_for_user(user_id, unread_only=True)
        for n in items:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
        self.db.flush()
        return len(items)
