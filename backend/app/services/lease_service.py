"""
Lease Agreement business logic.

Status machine (enforced here, not just in the DB):
  draft -> active -> (expired | terminated | renewed)
A renewal creates a NEW lease row (so the old contract's history/payment
schedule stays intact) and marks the old one RENEWED, linked via
renewed_from_lease_id.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.lease_repository import LeaseRepository, LeasePaymentInstallmentRepository
from app.repositories.owner_repository import OwnerRepository
from app.repositories.user_repository import UserRepository
from app.models.lease import LeaseAgreement, LeaseStatus, PaymentFrequency
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService

ENTITY_TYPE = "lease"

FREQUENCY_MONTHS = {
    PaymentFrequency.MONTHLY: 1,
    PaymentFrequency.QUARTERLY: 3,
    PaymentFrequency.SEMI_ANNUAL: 6,
    PaymentFrequency.ANNUAL: 12,
}


class LeaseService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = LeaseRepository(db)
        self.installment_repo = LeasePaymentInstallmentRepository(db)
        self.owner_repo = OwnerRepository(db)
        self.user_repo = UserRepository(db)
        self.audit = AuditService(db)
        self.notifications = NotificationService(db)

    # ---------------- CRUD ----------------
    def list_leases(self, params: PaginationParams, contract_status, owner_id, branch_id, expiring_soon, include_archived: bool = False):
        return self.repo.list_leases(
            page=params.page, page_size=params.page_size, search=params.search,
            contract_status=contract_status, owner_id=owner_id, branch_id=branch_id,
            expiring_soon=expiring_soon, sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
            include_archived=include_archived,
        )

    def get_lease(self, lease_id: int) -> LeaseAgreement:
        lease = self.repo.get_detail(lease_id)
        if not lease:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease agreement not found")
        return lease

    def create_lease(self, data: dict, actor_id: Optional[int]) -> LeaseAgreement:
        owner = self.owner_repo.get(data["owner_id"])
        if not owner:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid owner_id")
        if data.get("property_id"):
            from app.repositories.property_repository import PropertyRepository
            property_ = PropertyRepository(self.db).get(data["property_id"])
            if not property_:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid property_id")

        payload = dict(data)
        payload["contract_number"] = self.repo.next_contract_number()
        payload["contract_status"] = LeaseStatus.DRAFT
        lease = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, lease.id, "created", f"Lease {lease.contract_number} created (draft)", actor_id)
        self.audit.log_audit(ENTITY_TYPE, lease.id, "created", None, actor_id)
        self.db.commit()
        return self.repo.get_detail(lease.id)

    def update_lease(self, lease_id: int, data: dict, actor_id: Optional[int]) -> LeaseAgreement:
        lease = self.get_lease(lease_id)
        if lease.contract_status in (LeaseStatus.TERMINATED, LeaseStatus.RENEWED):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot edit a {lease.contract_status} lease")
        before = {k: getattr(lease, k) for k in data.keys()}
        self.repo.update(lease, data, actor_id=actor_id)
        after = {k: getattr(lease, k) for k in data.keys()}
        changes = self.audit.diff(before, after)
        if changes:
            self.audit.log_activity(ENTITY_TYPE, lease.id, "updated", f"Lease {lease.contract_number} updated", actor_id)
            self.audit.log_audit(ENTITY_TYPE, lease.id, "updated", changes, actor_id)
        self.db.commit()
        return self.repo.get_detail(lease.id)

    def delete_lease(self, lease_id: int, actor_id: Optional[int]) -> None:
        lease = self.get_lease(lease_id)
        # Same reasoning as RentalService.delete_contract: an ACTIVE
        # Master Lease means the company is currently paying this owner
        # for this property — deleting it directly would silently break
        # that relationship. Terminate first.
        if lease.contract_status == LeaseStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete an active lease agreement — terminate it first, then delete.",
            )
        # A Master Lease's own property may still have active tenant
        # contracts subleasing units within it — deleting the lease that
        # justifies the company having that building at all, while
        # tenants are still recorded as renting units in it, would leave
        # that occupancy pointing at nothing.
        if lease.property_id:
            from app.models.rental import RentalContract, RentalContractStatus
            from app.repositories.property_repository import PropertyRepository
            unit_ids = PropertyRepository(self.db).get_unit_ids(lease.property_id)
            active_sub_contracts = self.db.query(RentalContract).filter(
                RentalContract.property_id.in_([lease.property_id] + unit_ids),
                RentalContract.deleted_at.is_(None), RentalContract.contract_status == RentalContractStatus.ACTIVE,
            ).count()
            if active_sub_contracts > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot delete: {active_sub_contracts} active tenant contract(s) still exist in this lease's property. Terminate those first.",
                )
        self.repo.soft_delete(lease, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, lease.id, "deleted", f"Lease {lease.contract_number} deleted", actor_id)
        self.db.commit()

    def archive_lease(self, lease_id: int, actor_id: Optional[int]) -> LeaseAgreement:
        """Distinct from delete — see BaseRepository.archive(). Typically
        used on an expired/terminated lease you want out of the main
        list but still fully intact for lookups, reports, and audit."""
        lease = self.get_lease(lease_id)
        self.repo.archive(lease, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, lease.id, "archived", f"Lease {lease.contract_number} archived", actor_id)
        self.db.commit()
        return lease

    def unarchive_lease(self, lease_id: int, actor_id: Optional[int]) -> LeaseAgreement:
        lease = self.get_lease(lease_id)
        self.repo.unarchive(lease, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, lease.id, "unarchived", f"Lease {lease.contract_number} restored from archive", actor_id)
        self.db.commit()
        return lease

    # ---------------- Status transitions ----------------
    def activate_lease(self, lease_id: int, actor_id: Optional[int]) -> LeaseAgreement:
        lease = self.get_lease(lease_id)
        if lease.contract_status != LeaseStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only draft leases can be activated (current: {lease.contract_status})")
        lease.contract_status = LeaseStatus.ACTIVE
        self.audit.log_activity(ENTITY_TYPE, lease.id, "activated", f"Lease {lease.contract_number} activated", actor_id)
        self.db.commit()
        return self.repo.get_detail(lease.id)

    def terminate_lease(self, lease_id: int, terminated_date: date, reason: str, actor_id: Optional[int]) -> LeaseAgreement:
        lease = self.get_lease(lease_id)
        if lease.contract_status != LeaseStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active leases can be terminated (current: {lease.contract_status})")
        lease.contract_status = LeaseStatus.TERMINATED
        lease.terminated_date = terminated_date
        lease.termination_reason = reason
        self.audit.log_activity(ENTITY_TYPE, lease.id, "terminated", f"Lease {lease.contract_number} terminated: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, lease.id, "terminated", {"contract_status": {"old": "active", "new": "terminated"}}, actor_id)
        self.db.commit()
        return self.repo.get_detail(lease.id)

    def renew_lease(self, lease_id: int, new_end_date: date, new_start_date: Optional[date],
                     rent_amount: Optional[Decimal], notes_summary: Optional[str], actor_id: Optional[int]) -> LeaseAgreement:
        old_lease = self.get_lease(lease_id)
        if old_lease.contract_status != LeaseStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only active leases can be renewed (current: {old_lease.contract_status})")
        if not old_lease.is_renewable:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This lease is marked as non-renewable")

        start = new_start_date or (old_lease.end_date + timedelta(days=1))
        if new_end_date <= start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_end_date must be after the new start date")

        new_payload = {
            "owner_id": old_lease.owner_id,
            "property_id": old_lease.property_id,
            "branch_id": old_lease.branch_id,
            "property_reference": old_lease.property_reference,
            "start_date": start,
            "end_date": new_end_date,
            "is_renewable": old_lease.is_renewable,
            "renewal_notice_days": old_lease.renewal_notice_days,
            "payment_frequency": old_lease.payment_frequency,
            "rent_amount": rent_amount if rent_amount is not None else old_lease.rent_amount,
            "currency_id": old_lease.currency_id,
            "security_deposit_amount": old_lease.security_deposit_amount,
            "notes_summary": notes_summary or f"Renewed from {old_lease.contract_number}",
            "contract_number": self.repo.next_contract_number(),
            "contract_status": LeaseStatus.ACTIVE,
            "renewed_from_lease_id": old_lease.id,
        }
        new_lease = self.repo.create(new_payload, actor_id=actor_id)

        old_lease.contract_status = LeaseStatus.RENEWED

        self.audit.log_activity(ENTITY_TYPE, old_lease.id, "renewed", f"Lease {old_lease.contract_number} renewed as {new_lease.contract_number}", actor_id)
        self.audit.log_activity(ENTITY_TYPE, new_lease.id, "created", f"Lease {new_lease.contract_number} created via renewal of {old_lease.contract_number}", actor_id)
        self.db.commit()
        return self.repo.get_detail(new_lease.id)

    # ---------------- Payment Schedule ----------------
    def generate_schedule(self, lease_id: int, overwrite_existing: bool, actor_id: Optional[int]) -> list:
        lease = self.get_lease(lease_id)
        if lease.payment_frequency == PaymentFrequency.CUSTOM:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Custom payment frequency requires manually adding installments")

        existing = self.installment_repo.list_for_lease(lease_id)
        if existing and not overwrite_existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This lease already has installments. Pass overwrite_existing=true to regenerate.")
        for inst in existing:
            self.installment_repo.soft_delete(inst, actor_id=actor_id)

        installments = []
        if lease.payment_frequency == PaymentFrequency.ONE_TIME:
            installments.append(self.installment_repo.create({
                "lease_id": lease.id, "installment_number": 1, "due_date": lease.start_date, "amount": lease.rent_amount,
            }, actor_id=actor_id))
        else:
            step_months = FREQUENCY_MONTHS[lease.payment_frequency]
            current_due = lease.start_date
            number = 1
            while current_due <= lease.end_date:
                installments.append(self.installment_repo.create({
                    "lease_id": lease.id, "installment_number": number, "due_date": current_due, "amount": lease.rent_amount,
                }, actor_id=actor_id))
                current_due = current_due + relativedelta(months=step_months)
                number += 1

        self.audit.log_activity(ENTITY_TYPE, lease.id, "schedule_generated", f"Payment schedule generated ({len(installments)} installment(s))", actor_id)
        self.db.commit()
        return self.installment_repo.list_for_lease(lease_id)

    def add_installment(self, lease_id: int, data: dict, actor_id: Optional[int]):
        self.get_lease(lease_id)
        data["lease_id"] = lease_id
        data["installment_number"] = self.installment_repo.next_installment_number(lease_id)
        inst = self.installment_repo.create(data, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, lease_id, "installment_added", f"Installment #{inst.installment_number} added", actor_id)
        self.db.commit()
        return inst

    def update_installment(self, lease_id: int, installment_id: int, data: dict, actor_id: Optional[int]):
        inst = self.installment_repo.get(installment_id)
        if not inst or inst.lease_id != lease_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
        was_pending = inst.payment_status == "pending"
        self.installment_repo.update(inst, data, actor_id=actor_id)
        if data.get("payment_status") == "paid" and was_pending:
            self.audit.log_activity(ENTITY_TYPE, lease_id, "installment_paid", f"Installment #{inst.installment_number} marked paid", actor_id)
        self.db.commit()
        return inst

    def delete_installment(self, lease_id: int, installment_id: int, actor_id: Optional[int]):
        inst = self.installment_repo.get(installment_id)
        if not inst or inst.lease_id != lease_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
        self.installment_repo.soft_delete(inst, actor_id=actor_id)
        self.db.commit()

    # ---------------- Dashboard & Renewal Reminders ----------------
    def dashboard(self) -> dict:
        return self.repo.dashboard_counts()

    def run_maintenance_sweep(self, actor_id: Optional[int] = None) -> dict:
        """
        Idempotent housekeeping pass: expires past-due active leases, flags
        overdue installments, and sends (in-app) renewal reminder
        notifications for leases entering their renewal window.

        Phase 3 has no background job scheduler yet, so this is exposed as
        an on-demand endpoint (POST /leases/maintenance/run). In production,
        wire this to a daily cron / Azure Function timer trigger — see
        docs/phase3-renewal-reminders.md.
        """
        expired_count = self.repo.auto_expire_overdue_leases()
        overdue_count = self.installment_repo.mark_overdue_past_due()
        reminders_sent = self._send_renewal_reminders()
        self.db.commit()
        return {
            "leases_auto_expired": expired_count,
            "installments_marked_overdue": overdue_count,
            "renewal_reminders_sent": reminders_sent,
        }

    def _send_renewal_reminders(self) -> int:
        expiring = self.repo.get_expiring_soon()
        admin_ids = list(self.db.execute(
            select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
        ).scalars().all())

        sent = 0
        for lease in expiring:
            if lease.renewal_reminder_sent:
                continue
            for admin_id in admin_ids:
                self.notifications.notify(
                    recipient_id=admin_id,
                    title="Lease renewal due soon",
                    message=f"Lease {lease.contract_number} ({lease.owner_display_name or 'owner'}) expires in {lease.days_until_expiry} day(s).",
                    notification_type="warning",
                    entity_type=ENTITY_TYPE,
                    entity_id=lease.id,
                )
            lease.renewal_reminder_sent = True
            sent += 1
        return sent
