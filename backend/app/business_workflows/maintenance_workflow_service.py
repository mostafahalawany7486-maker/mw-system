"""
MaintenanceWorkflowService

Orchestrates the maintenance request lifecycle (app/services/
maintenance_service.py) together with the financial ledger
(app/services/financial_service.py) and notifications:

  - report_and_triage: creates a request and immediately notifies admins,
    escalating the notification type for urgent/high priority requests.
  - complete_and_settle: completes a request AND, if it accrued any
    material/labor cost, books that cost as an EXPENSE transaction
    against the property (which auto-posts to the general ledger via
    the existing JournalEntryService.auto_post_from_transaction, exactly
    like every other FinancialService.create_transaction call) — closing
    the loop between "work is done" and "the cost is on the books"
    without requiring a second manual step.
"""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.models.maintenance import MaintenancePriority
from app.models.financial import TransactionType
from app.services.maintenance_service import MaintenanceService
from app.services.financial_service import FinancialService
from app.business_workflows.notification_workflow_service import NotificationWorkflowService
from app.business_workflows.common import WorkflowResult

ENTITY_TYPE = "maintenance_request"

ESCALATED_PRIORITIES = {MaintenancePriority.HIGH, MaintenancePriority.URGENT}


class MaintenanceWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.maintenance_service = MaintenanceService(db)
        self.financial_service = FinancialService(db)
        self.notification_workflow = NotificationWorkflowService(db)

    def report_and_triage(self, data: dict, actor_id: Optional[int]) -> WorkflowResult:
        """Creates a maintenance request and notifies admins, using a
        higher-urgency notification for high/urgent priority requests so
        they aren't buried alongside routine ones.
        """
        request = self.maintenance_service.create_request(data, actor_id=actor_id)

        is_escalated = request.priority in ESCALATED_PRIORITIES
        sent = self.notification_workflow.notify_admins(
            title="Urgent maintenance request reported" if is_escalated else "Maintenance request reported",
            message=f"{request.request_number}: {request.title} (priority: {request.priority})",
            notification_type="warning" if is_escalated else "info",
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
        )

        metrics = self.maintenance_service.dashboard()
        return WorkflowResult(
            workflow="maintenance.report_and_triage",
            message=f"Maintenance request {request.request_number} reported"
                    + (" and flagged as high priority." if is_escalated else "."),
            data=request,
            metrics=metrics,
            notifications_sent=sent,
        )

    def complete_and_settle(
        self,
        request_id: int,
        completed_date: date,
        actor_id: Optional[int],
        account_id: Optional[int] = None,
    ) -> WorkflowResult:
        """Completes a request and, if it has any accrued cost and an
        `account_id` was provided to pay it from, books that cost as an
        expense transaction attributable to the request's property.

        `account_id` is optional: a caller that only wants to mark work
        done (without also settling the expense in the same call) can
        omit it, and the cost simply isn't posted yet — nothing here
        silently skips or fabricates a payment source.
        """
        request = self.maintenance_service.complete_request(request_id, completed_date, actor_id=actor_id)

        accounting_events: list[str] = []
        warnings: list[str] = []
        cost = request.total_actual_cost

        if cost > 0 and account_id is not None:
            txn = self.financial_service.create_transaction({
                "transaction_type": TransactionType.EXPENSE,
                "amount": cost,
                "account_id": account_id,
                "property_id": request.property_id,
                "transaction_date": completed_date,
                "description": f"Maintenance expense for {request.request_number}: {request.title}",
            }, actor_id=actor_id)
            accounting_events.append(f"Transaction {txn.transaction_number} posted for {cost} expense")
        elif cost > 0:
            warnings.append(
                f"Request accrued {cost} in cost but no account_id was provided — expense was not posted."
            )

        sent = self.notification_workflow.notify_admins(
            title="Maintenance request completed",
            message=f"{request.request_number} completed"
                    + (f" — {cost} in cost recorded." if accounting_events else "."),
            notification_type="success",
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
        )

        metrics = self.maintenance_service.dashboard()
        return WorkflowResult(
            workflow="maintenance.complete_and_settle",
            message=f"Maintenance request {request.request_number} completed.",
            data=request,
            metrics=metrics,
            notifications_sent=sent,
            accounting_events=accounting_events,
            warnings=warnings,
        )
