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

    def list_for_user(self, user_id: int, unread_only: bool = False, limit: Optional[int] = 50) -> list[Notification]:
        return self.repo.list_for_user(user_id, unread_only, limit=limit)

    def unread_count(self, user_id: int) -> int:
        return self.repo.unread_count(user_id)

    def mark_read(self, notification: Notification) -> Notification:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        self.db.commit()
        return notification

    def mark_all_read(self, user_id: int) -> int:
        # Deliberately uncapped (limit=None) — this needs to actually clear
        # every unread notification, not just the most recent 50 shown in
        # the dropdown. Found and fixed together during the production
        # audit: capping list_for_user() without this override would have
        # silently left older unread notifications stuck forever for any
        # user with more than 50 of them.
        items = self.repo.list_for_user(user_id, unread_only=True, limit=None)
        for n in items:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
        count = len(items)
        self.db.commit()
        return count
