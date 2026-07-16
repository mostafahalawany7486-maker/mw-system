"""
Centralized logging service. Every service that mutates data calls this so
Activity Log and Audit Log stay consistent across all modules, present and
future, without duplicating logging code.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.system_repository import ActivityLogRepository, AuditLogRepository
from app.models.system import ActivityLog, AuditLog


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.activity_repo = ActivityLogRepository(db)
        self.audit_repo = AuditLogRepository(db)

    def log_activity(
        self, entity_type: str, entity_id: int, action: str, description: str, actor_id: Optional[int]
    ) -> ActivityLog:
        return self.activity_repo.create({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "description": description,
            "actor_id": actor_id,
        })

    def log_audit(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        changed_fields: Optional[dict],
        actor_id: Optional[int],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        return self.audit_repo.create({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "changed_fields": changed_fields,
            "actor_id": actor_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
        })

    @staticmethod
    def diff(before: dict, after: dict) -> dict:
        """Compute a {field: {old, new}} diff for audit logging."""
        changes = {}
        keys = set(before.keys()) | set(after.keys())
        for key in keys:
            old_val = before.get(key)
            new_val = after.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        return changes
