"""
OwnerSettlementWorkflowService

Orchestrates paying an Owner what the company owes them under a Lease
Agreement (the owner-side counterpart to PaymentWorkflowService, which
handles money coming IN from tenants — this handles money going OUT to
owners). No new payment mechanism is introduced: this reuses
FinancialService.create_transaction() with transaction_type=
OWNER_PAYMENT and lease_installment_id set, which already (see
app/services/financial_service.py):
  - marks the linked LeasePaymentInstallment as paid,
  - auto-posts the corresponding journal entry via
    JournalEntryService.auto_post_from_transaction.

This workflow's own responsibility is picking *which* installment(s) to
settle, validating they're actually payable, and notifying admins —
work that today has no single entry point and would otherwise mean
looking up a lease, finding the right installment, and calling
create_transaction by hand.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.lease import InstallmentStatus, LeaseStatus
from app.models.financial import TransactionType
from app.services.lease_service import LeaseService
from app.services.financial_service import FinancialService
from app.business_workflows.notification_workflow_service import NotificationWorkflowService
from app.business_workflows.common import WorkflowResult

ENTITY_TYPE = "lease"
SETTLEABLE_STATUSES = (InstallmentStatus.PENDING, InstallmentStatus.OVERDUE)


class OwnerSettlementWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.lease_service = LeaseService(db)
        self.financial_service = FinancialService(db)
        self.notification_workflow = NotificationWorkflowService(db)

    def _get_settleable_installment(self, lease, installment_id: int):
        installment = next((i for i in lease.installments if i.id == installment_id), None)
        if not installment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Installment {installment_id} not found on lease {lease.contract_number}",
            )
        if installment.payment_status not in SETTLEABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Installment #{installment.installment_number} is already "
                       f"'{installment.payment_status}' and cannot be settled again",
            )
        return installment

    def settle_owner_installment(
        self,
        lease_id: int,
        installment_id: int,
        account_id: int,
        transaction_date: date,
        actor_id: Optional[int],
        payment_method: Optional[str] = None,
        reference_number: Optional[str] = None,
    ) -> WorkflowResult:
        """Pays out a single owner lease installment."""
        lease = self.lease_service.get_lease(lease_id)
        installment = self._get_settleable_installment(lease, installment_id)

        txn = self.financial_service.create_transaction({
            "transaction_type": TransactionType.OWNER_PAYMENT,
            "amount": installment.amount,
            "account_id": account_id,
            "owner_id": lease.owner_id,
            "lease_installment_id": installment.id,
            "payment_method": payment_method,
            "reference_number": reference_number,
            "transaction_date": transaction_date,
            "description": f"Owner settlement for lease {lease.contract_number}, "
                            f"installment #{installment.installment_number}",
        }, actor_id=actor_id)

        accounting_events = [f"Transaction {txn.transaction_number} posted for {installment.amount} owner payment"]

        sent = self.notification_workflow.notify_admins(
            title="Owner settlement processed",
            message=f"Paid installment #{installment.installment_number} ({installment.amount}) "
                    f"on lease {lease.contract_number}.",
            notification_type="success",
            entity_type=ENTITY_TYPE,
            entity_id=lease.id,
        )

        balances = self.financial_service.outstanding_balances()
        metrics = {
            "installment_amount": installment.amount,
            "total_owner_outstanding": balances["total_owner_outstanding"],
        }

        return WorkflowResult(
            workflow="owner_settlement.settle_installment",
            message=f"Installment #{installment.installment_number} on lease {lease.contract_number} settled.",
            data=self.lease_service.get_lease(lease_id),
            metrics=metrics,
            notifications_sent=sent,
            accounting_events=accounting_events,
        )

    def run_bulk_owner_settlement(
        self,
        account_id: int,
        transaction_date: date,
        actor_id: Optional[int],
        owner_id: Optional[int] = None,
        payment_method: Optional[str] = None,
    ) -> WorkflowResult:
        """Settles every pending/overdue installment across an owner's
        active leases (or, if `owner_id` is omitted, across ALL owners'
        active leases). A failure settling one installment does not
        abort the rest — results are collected per-installment so a
        caller can see exactly what was and wasn't paid out.
        """
        from app.schemas.common import PaginationParams

        leases, _ = self.lease_service.list_leases(
            PaginationParams(page=1, page_size=1000), contract_status=LeaseStatus.ACTIVE,
            owner_id=owner_id, branch_id=None, expiring_soon=None,
        )

        results = []
        accounting_events: list[str] = []
        succeeded = 0
        failed = 0
        total_paid = Decimal("0")

        for lease_summary in leases:
            lease = self.lease_service.get_lease(lease_summary.id)
            pending = [i for i in lease.installments if i.payment_status in SETTLEABLE_STATUSES]
            for installment in pending:
                try:
                    result = self.settle_owner_installment(
                        lease.id, installment.id, account_id, transaction_date, actor_id=actor_id,
                        payment_method=payment_method,
                    )
                    results.append({
                        "lease_id": lease.id, "installment_id": installment.id,
                        "success": True, "amount": installment.amount,
                    })
                    accounting_events.extend(result.accounting_events)
                    total_paid += installment.amount
                    succeeded += 1
                except HTTPException as exc:
                    results.append({
                        "lease_id": lease.id, "installment_id": installment.id,
                        "success": False, "error": exc.detail,
                    })
                    failed += 1

        message = (
            f"Bulk owner settlement: {succeeded} installment(s) paid "
            f"({total_paid} total), {failed} failed."
        )
        sent = self.notification_workflow.notify_admins(
            title="Bulk owner settlement completed",
            message=message,
            notification_type="warning" if failed else "success",
            entity_type=ENTITY_TYPE,
        )

        return WorkflowResult(
            workflow="owner_settlement.run_bulk",
            message=message,
            data=results,
            metrics={"succeeded": succeeded, "failed": failed, "total_paid": total_paid},
            notifications_sent=sent,
            accounting_events=accounting_events,
        )
