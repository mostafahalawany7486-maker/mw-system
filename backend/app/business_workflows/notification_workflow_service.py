"""
NotificationWorkflowService

Cross-cutting notification orchestration used both directly (e.g. a
scheduled "run the daily notification sweep" job) and internally by the
other workflow services in this package, so the "notify every active
superuser" fan-out pattern lives in exactly one place instead of being
copy-pasted per workflow (it was already duplicated between
LeaseService._send_renewal_reminders and RentalService._send_renewal_reminders
before this layer existed — see app/services/lease_service.py and
app/services/rental_service.py).

This service never touches SQLAlchemy models directly for writes: it
calls NotificationService (existing) for delivery, and only reads
User rows to resolve "who is an admin" — the same read the two services
above already perform.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.lease_service import LeaseService
from app.services.rental_service import RentalService
from app.services.financial_service import FinancialService
from app.business_workflows.common import WorkflowResult


class NotificationWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.notifications = NotificationService(db)
        self.lease_service = LeaseService(db)
        self.rental_service = RentalService(db)
        self.financial_service = FinancialService(db)

    # ---------------- Shared fan-out helper ----------------
    def notify_admins(
        self,
        title: str,
        message: str,
        notification_type: str = "info",
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
    ) -> int:
        """Notify every active superuser. Returns how many were notified.

        This is the single place the rest of the workflow layer should
        call for "let the back office know something happened" — it does
        not replace NotificationService.notify() (still the underlying
        delivery mechanism), it just centralizes recipient resolution.
        """
        admin_ids = list(self.db.execute(
            select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
        ).scalars().all())
        for admin_id in admin_ids:
            self.notifications.notify(
                recipient_id=admin_id,
                title=title,
                message=message,
                notification_type=notification_type,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        return len(admin_ids)

    # ---------------- Workflows ----------------
    def run_daily_notification_sweep(self, actor_id: Optional[int] = None) -> WorkflowResult:
        """Runs the existing per-module housekeeping sweeps back-to-back
        and folds their results into one summary notification.

        Orchestrates (does not reimplement):
          - LeaseService.run_maintenance_sweep()      (owner-side leases)
          - RentalService.run_maintenance_sweep()     (tenant-side rentals)
          - FinancialService.maintenance_sweep()      (invoice overdue sweep)

        Each of those already sends its own targeted notifications (e.g.
        renewal reminders); this workflow additionally posts one rollup
        notification so admins get a single "here's what housekeeping did
        today" summary instead of having to piece it together from three
        separate endpoints.
        """
        lease_result = self.lease_service.run_maintenance_sweep(actor_id=actor_id)
        rental_result = self.rental_service.run_maintenance_sweep(actor_id=actor_id)
        invoice_result = self.financial_service.maintenance_sweep(actor_id=actor_id)

        metrics = {
            "leases_auto_expired": lease_result["leases_auto_expired"],
            "lease_installments_marked_overdue": lease_result["installments_marked_overdue"],
            "lease_renewal_reminders_sent": lease_result["renewal_reminders_sent"],
            "rentals_auto_expired": rental_result["contracts_auto_expired"],
            "rental_installments_marked_overdue": rental_result["installments_marked_overdue"],
            "rental_late_fees_assessed": rental_result["late_fees_assessed"],
            "rental_renewal_reminders_sent": rental_result["renewal_reminders_sent"],
            "invoices_marked_overdue": invoice_result["invoices_marked_overdue"],
        }

        summary = (
            f"Daily sweep: {metrics['leases_auto_expired']} lease(s) expired, "
            f"{metrics['rentals_auto_expired']} rental(s) expired, "
            f"{metrics['invoices_marked_overdue']} invoice(s) marked overdue, "
            f"{metrics['lease_renewal_reminders_sent'] + metrics['rental_renewal_reminders_sent']} "
            "renewal reminder(s) sent."
        )
        sent = self.notify_admins(
            title="Daily notification sweep completed",
            message=summary,
            notification_type="info",
            entity_type="business_workflow",
        )

        return WorkflowResult(
            workflow="notification.daily_sweep",
            message=summary,
            data=metrics,
            metrics=metrics,
            notifications_sent=sent,
        )

    def notify_outstanding_balances(self, actor_id: Optional[int] = None) -> WorkflowResult:
        """Summarizes current tenant/owner outstanding balances (via the
        existing FinancialService.outstanding_balances()) and pushes one
        notification to admins. Read-only — triggers no accounting
        events, since it doesn't move any money itself (see
        PaymentWorkflowService / OwnerSettlementWorkflowService for that).
        """
        balances = self.financial_service.outstanding_balances()
        metrics = {
            "tenants_with_outstanding_balance": len(balances["tenants"]),
            "owners_with_outstanding_balance": len(balances["owners"]),
            "total_tenant_outstanding": balances["total_tenant_outstanding"],
            "total_owner_outstanding": balances["total_owner_outstanding"],
        }
        message = (
            f"{metrics['tenants_with_outstanding_balance']} tenant(s) owe "
            f"{metrics['total_tenant_outstanding']} in total; "
            f"{metrics['owners_with_outstanding_balance']} owner(s) are owed "
            f"{metrics['total_owner_outstanding']} in total."
        )
        sent = self.notify_admins(
            title="Outstanding balances summary",
            message=message,
            notification_type="warning" if (balances["tenants"] or balances["owners"]) else "info",
            entity_type="business_workflow",
        )
        return WorkflowResult(
            workflow="notification.outstanding_balances",
            message=message,
            data=balances,
            metrics=metrics,
            notifications_sent=sent,
        )
