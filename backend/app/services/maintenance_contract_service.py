"""
Maintenance Contract business logic.

Status machine (enforced here, not just in the DB) — deliberately the same
shape as LeaseAgreement (Phase 3):
  draft -> active -> (expired | terminated | renewed)
Renewal creates a NEW contract row (so the old contract's history/linked
maintenance requests stay intact) and marks the old one RENEWED, linked
via renewed_from_contract_id.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.maintenance_contract_repository import MaintenanceContractRepository
from app.repositories.maintenance_repository import ContractorRepository
from app.repositories.property_repository import PropertyRepository
from app.models.maintenance_contract import MaintenanceContract, MaintenanceContractStatus, ContractVisitFrequency
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

ENTITY_TYPE = "maintenance_contract"

FREQUENCY_MONTHS = {
    ContractVisitFrequency.MONTHLY: 1,
    ContractVisitFrequency.QUARTERLY: 3,
    ContractVisitFrequency.SEMI_ANNUAL: 6,
    ContractVisitFrequency.ANNUAL: 12,
}


class MaintenanceContractService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MaintenanceContractRepository(db)
        self.property_repo = PropertyRepository(db)
        self.contractor_repo = ContractorRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    # ---------------- CRUD ----------------
    def list_contracts(self, params: PaginationParams, contract_status, property_id, contractor_id, service_type, expiring_soon):
        return self.repo.list_contracts(
            page=params.page, page_size=params.page_size, search=params.search,
            contract_status=contract_status, property_id=property_id, contractor_id=contractor_id,
            service_type=service_type, expiring_soon=expiring_soon, sort_dir=params.sort_dir or "asc",
        )

    def get_contract(self, contract_id: int) -> MaintenanceContract:
        contract = self.repo.get_detail(contract_id)
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance contract not found")
        return contract

    def create_contract(self, data: dict, actor_id: Optional[int]) -> MaintenanceContract:
        if not self.property_repo.get(data["property_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid property_id")
        if not self.contractor_repo.get(data["contractor_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contractor_id")
        if data["end_date"] <= data["start_date"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date must be after start_date")

        payload = dict(data)
        payload["contract_number"] = self.repo.next_contract_number()
        payload["contract_status"] = MaintenanceContractStatus.DRAFT
        if not payload.get("next_service_due_date"):
            months = FREQUENCY_MONTHS.get(payload.get("visit_frequency"))
            if months:
                payload["next_service_due_date"] = payload["start_date"] + relativedelta(months=months)

        contract = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, contract.id, "created", f"Maintenance contract {contract.contract_number} created (draft)", actor_id)
        self.audit.log_audit(ENTITY_TYPE, contract.id, "created", None, actor_id)
        self.db.commit()
        return self.repo.get_detail(contract.id)

    def update_contract(self, contract_id: int, data: dict, actor_id: Optional[int]) -> MaintenanceContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status in (MaintenanceContractStatus.TERMINATED, MaintenanceContractStatus.RENEWED):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot edit a {contract.contract_status} contract")
        if data.get("contractor_id") and not self.contractor_repo.get(data["contractor_id"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid contractor_id")

        before = {k: getattr(contract, k) for k in data.keys()}
        self.repo.update(contract, data, actor_id=actor_id)
        after = {k: getattr(contract, k) for k in data.keys()}
        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity(ENTITY_TYPE, contract.id, "updated", f"Maintenance contract {contract.contract_number} updated", actor_id)
            self.audit.log_audit(ENTITY_TYPE, contract.id, "updated", changes, actor_id)
        self.db.commit()
        return self.repo.get_detail(contract.id)

    def delete_contract(self, contract_id: int, actor_id: Optional[int]) -> None:
        contract = self.get_contract(contract_id)
        self.repo.soft_delete(contract, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, contract.id, "deleted", f"Maintenance contract {contract.contract_number} deleted", actor_id)
        self.db.commit()

    # ---------------- Status transitions ----------------
    def activate_contract(self, contract_id: int, actor_id: Optional[int]) -> MaintenanceContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status != MaintenanceContractStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only draft contracts can be activated (current: {contract.contract_status})")
        contract.contract_status = MaintenanceContractStatus.ACTIVE
        self.audit.log_activity(ENTITY_TYPE, contract.id, "activated", f"Maintenance contract {contract.contract_number} activated", actor_id)
        self.db.commit()
        return self.repo.get_detail(contract.id)

    def terminate_contract(self, contract_id: int, terminated_date: date, reason: str, actor_id: Optional[int]) -> MaintenanceContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status != MaintenanceContractStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active contracts can be terminated (current: {contract.contract_status})")
        contract.contract_status = MaintenanceContractStatus.TERMINATED
        contract.terminated_date = terminated_date
        contract.termination_reason = reason
        self.audit.log_activity(ENTITY_TYPE, contract.id, "terminated", f"Maintenance contract {contract.contract_number} terminated: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, contract.id, "terminated", {"contract_status": {"old": "active", "new": "terminated"}}, actor_id)
        self.db.commit()
        return self.repo.get_detail(contract.id)

    def renew_contract(self, contract_id: int, new_end_date: date, new_start_date: Optional[date],
                        annual_cost: Optional[Decimal], notes: Optional[str], actor_id: Optional[int]) -> MaintenanceContract:
        old_contract = self.get_contract(contract_id)
        if old_contract.contract_status != MaintenanceContractStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active contracts can be renewed (current: {old_contract.contract_status})")
        if not old_contract.is_renewable:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This contract is marked as non-renewable")

        start = new_start_date or (old_contract.end_date + timedelta(days=1))
        if new_end_date <= start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_end_date must be after the new start date")

        months = FREQUENCY_MONTHS.get(old_contract.visit_frequency)
        new_payload = {
            "property_id": old_contract.property_id,
            "contractor_id": old_contract.contractor_id,
            "service_type": old_contract.service_type,
            "title": old_contract.title,
            "description": old_contract.description,
            "start_date": start,
            "end_date": new_end_date,
            "visit_frequency": old_contract.visit_frequency,
            "visits_per_year": old_contract.visits_per_year,
            "next_service_due_date": (start + relativedelta(months=months)) if months else None,
            "annual_cost": annual_cost if annual_cost is not None else old_contract.annual_cost,
            "currency_id": old_contract.currency_id,
            "is_renewable": old_contract.is_renewable,
            "renewal_notice_days": old_contract.renewal_notice_days,
            "notes": notes or f"Renewed from {old_contract.contract_number}",
            "contract_number": self.repo.next_contract_number(),
            "contract_status": MaintenanceContractStatus.ACTIVE,
            "renewed_from_contract_id": old_contract.id,
        }
        new_contract = self.repo.create(new_payload, actor_id=actor_id)

        old_contract.contract_status = MaintenanceContractStatus.RENEWED

        self.audit.log_activity(ENTITY_TYPE, old_contract.id, "renewed", f"Maintenance contract {old_contract.contract_number} renewed as {new_contract.contract_number}", actor_id)
        self.audit.log_activity(ENTITY_TYPE, new_contract.id, "created", f"Maintenance contract {new_contract.contract_number} created via renewal of {old_contract.contract_number}", actor_id)
        self.db.commit()
        return self.repo.get_detail(new_contract.id)

    # ---------------- Service visits ----------------
    def log_service_visit(self, contract_id: int, visit_date: date, notes: Optional[str], actor_id: Optional[int]) -> MaintenanceContract:
        contract = self.get_contract(contract_id)
        if contract.contract_status != MaintenanceContractStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active contracts can log a service visit (current: {contract.contract_status})")

        months = FREQUENCY_MONTHS.get(contract.visit_frequency)
        if months:
            contract.next_service_due_date = visit_date + relativedelta(months=months)
        note_line = f"Service visit logged on {visit_date.isoformat()}" + (f": {notes}" if notes else "")
        self.audit.log_activity(ENTITY_TYPE, contract.id, "service_visit_logged", f"{contract.contract_number} — {note_line}", actor_id)
        self.db.commit()
        return self.repo.get_detail(contract.id)

    # ---------------- Dashboard & sweep ----------------
    def dashboard(self) -> dict:
        counts = self.repo.dashboard_counts()
        counts["upcoming"] = self.repo.get_expiring_soon()[:10]
        return counts

    def run_maintenance_sweep(self, actor_id: Optional[int] = None) -> dict:
        """
        Idempotent housekeeping pass: expires past-due active contracts and
        sends (in-app) renewal reminder notifications for contracts entering
        their renewal window — same on-demand pattern as Phase 3/7 (no
        background job scheduler exists in this stack yet; wire this to a
        daily cron / Azure Function timer trigger in production, exactly as
        documented in docs/phase3-renewal-reminders.md).
        """
        expired_count = self.repo.auto_expire_overdue_contracts()
        reminders_sent = self._send_renewal_reminders()
        service_due_notified = self._send_service_due_notifications()
        self.db.commit()
        return {
            "contracts_auto_expired": expired_count,
            "renewal_reminders_sent": reminders_sent,
            "service_due_notifications_sent": service_due_notified,
        }

    def _admin_ids(self) -> list[int]:
        return list(self.db.execute(
            select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
        ).scalars().all())

    def _send_renewal_reminders(self) -> int:
        expiring = self.repo.get_expiring_soon()
        admin_ids = self._admin_ids()

        sent = 0
        for contract in expiring:
            if contract.renewal_reminder_sent:
                continue
            for admin_id in admin_ids:
                self.notifications.notify(
                    recipient_id=admin_id,
                    title="Maintenance contract renewal due soon",
                    message=f"Contract {contract.contract_number} ({contract.contractor_name or 'contractor'} — {contract.property_title or 'property'}) expires in {contract.days_until_expiry} day(s).",
                    notification_type="warning",
                    entity_type=ENTITY_TYPE,
                    entity_id=contract.id,
                )
            contract.renewal_reminder_sent = True
            sent += 1
        return sent

    def _send_service_due_notifications(self) -> int:
        """Separate from renewal reminders: flags contracts whose *next
        scheduled visit* (e.g. this quarter's elevator inspection) is due
        soon or overdue, regardless of how much contract term remains."""
        due_soon = self.repo.get_service_due_soon()
        admin_ids = self._admin_ids()

        sent = 0
        for contract in due_soon:
            status_word = "overdue" if contract.is_service_overdue else "due soon"
            for admin_id in admin_ids:
                self.notifications.notify(
                    recipient_id=admin_id,
                    title=f"Scheduled maintenance visit {status_word}",
                    message=f"{contract.service_type.title()} service under contract {contract.contract_number} ({contract.property_title or 'property'}) is {status_word} — next visit: {contract.next_service_due_date}.",
                    notification_type="warning" if contract.is_service_overdue else "info",
                    entity_type=ENTITY_TYPE,
                    entity_id=contract.id,
                )
            sent += 1
        return sent
