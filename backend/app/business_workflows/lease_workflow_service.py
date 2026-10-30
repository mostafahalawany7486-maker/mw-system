"""
LeaseWorkflowService

Orchestrates the Owner <-> Company Lease Agreement lifecycle
(app/services/lease_service.py) into complete business processes. This
service does not reimplement any lease business rule — LeaseService
remains the single source of truth for lease state transitions; this
layer only sequences calls to it (and to notifications/dashboards)
that, in production, a staff member would otherwise have to trigger by
hand across several screens.

Workflows:
  - activate_lease_with_schedule: activate a draft lease AND generate
    its payment installment schedule in one step, then notify admins.
  - renew_lease_and_reschedule: renew an active lease AND generate the
    new contract's schedule, then notify admins.
  - terminate_lease_with_notice: terminate a lease with a mandatory
    reason, notify admins, and flag the security deposit for follow-up.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services.lease_service import LeaseService
from app.business_workflows.notification_workflow_service import NotificationWorkflowService
from app.business_workflows.common import WorkflowResult

ENTITY_TYPE = "lease"


class LeaseWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.lease_service = LeaseService(db)
        self.notification_workflow = NotificationWorkflowService(db)

    def activate_lease_with_schedule(
        self, lease_id: int, actor_id: Optional[int], generate_schedule: bool = True,
    ) -> WorkflowResult:
        """Activates a draft lease and, unless the caller opts out,
        immediately generates its installment schedule — the two steps
        that always happen together in practice, but are two separate
        LeaseService calls today (activate_lease / generate_schedule).
        """
        lease = self.lease_service.activate_lease(lease_id, actor_id=actor_id)

        warnings: list[str] = []
        installments = []
        if generate_schedule:
            try:
                installments = self.lease_service.generate_schedule(
                    lease_id, overwrite_existing=False, actor_id=actor_id,
                )
            except HTTPException as exc:
                # A schedule already existing is not fatal to activation —
                # surface it as a warning instead of failing the whole
                # workflow, since the lease itself activated successfully.
                warnings.append(f"Schedule not generated: {exc.detail}")

        sent = self.notification_workflow.notify_admins(
            title="Lease activated",
            message=f"Lease {lease.contract_number} is now active"
            + (f" with {len(installments)} installment(s) scheduled." if installments else "."),
            notification_type="success",
            entity_type=ENTITY_TYPE,
            entity_id=lease.id,
        )

        metrics = self.lease_service.dashboard()
        return WorkflowResult(
            workflow="lease.activate_with_schedule",
            message=f"Lease {lease.contract_number} activated"
            + (f" and {len(installments)} installment(s) generated." if installments else "."),
            data=lease,
            metrics=metrics,
            notifications_sent=sent,
            warnings=warnings,
        )

    def renew_lease_and_reschedule(
        self,
        lease_id: int,
        new_end_date: date,
        actor_id: Optional[int],
        new_start_date: Optional[date] = None,
        rent_amount: Optional[Decimal] = None,
        notes_summary: Optional[str] = None,
    ) -> WorkflowResult:
        """Renews an active lease into a new contract row (existing
        renew_lease business rule: renewal is a NEW lease so payment
        history stays intact) and generates the new lease's schedule in
        the same step, then notifies admins.
        """
        new_lease = self.lease_service.renew_lease(
            lease_id, new_end_date, new_start_date, rent_amount, notes_summary, actor_id=actor_id,
        )

        warnings: list[str] = []
        installments = []
        try:
            installments = self.lease_service.generate_schedule(
                new_lease.id, overwrite_existing=False, actor_id=actor_id,
            )
        except HTTPException as exc:
            warnings.append(f"Schedule not generated for renewed lease: {exc.detail}")

        sent = self.notification_workflow.notify_admins(
            title="Lease renewed",
            message=f"Lease renewed as {new_lease.contract_number}, expiring {new_lease.end_date}.",
            notification_type="info",
            entity_type=ENTITY_TYPE,
            entity_id=new_lease.id,
        )

        metrics = self.lease_service.dashboard()
        return WorkflowResult(
            workflow="lease.renew_and_reschedule",
            message=f"Lease renewed as {new_lease.contract_number} with "
                    f"{len(installments)} installment(s) scheduled.",
            data=new_lease,
            metrics=metrics,
            notifications_sent=sent,
            warnings=warnings,
        )

    def terminate_lease_with_notice(
        self, lease_id: int, terminated_date: date, reason: str, actor_id: Optional[int],
    ) -> WorkflowResult:
        """Terminates a lease and notifies admins. Enforces (at the
        workflow level) that a termination reason is actually provided —
        LeaseService.terminate_lease accepts an empty string today, but a
        workflow-initiated termination should always be explainable.
        """
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A termination reason is required to terminate a lease via this workflow",
            )

        lease = self.lease_service.terminate_lease(lease_id, terminated_date, reason, actor_id=actor_id)

        warnings = []
        if lease.security_deposit_status == "held":
            warnings.append(
                "Security deposit is still marked as held — settle it via the security deposit "
                "workflow/endpoint before closing this lease out financially."
            )

        sent = self.notification_workflow.notify_admins(
            title="Lease terminated",
            message=f"Lease {lease.contract_number} terminated: {reason}",
            notification_type="warning",
            entity_type=ENTITY_TYPE,
            entity_id=lease.id,
        )

        metrics = self.lease_service.dashboard()
        return WorkflowResult(
            workflow="lease.terminate_with_notice",
            message=f"Lease {lease.contract_number} terminated.",
            data=lease,
            metrics=metrics,
            notifications_sent=sent,
            warnings=warnings,
        )
