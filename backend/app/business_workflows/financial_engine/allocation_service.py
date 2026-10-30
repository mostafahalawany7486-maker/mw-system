"""
allocation_service.py

Spec: "Prevent invalid allocations." Deliberately does not introduce a
second allocation table. Tenant-side allocations (one payment covering
one or more invoices) are already fully implemented in
business_workflows/payment/ (Phase 16, PaymentAllocation) — this module
validates a proposed allocation list with the exact same rule
(financial_validator.py's validate_allocation_sum) before it's handed
to PaymentWorkflowService.create_payment(), rather than re-implementing
allocation itself. Owner-side "allocation" (a recoverable expense
against a specific property/category) already goes through
OwnerLedgerEntry directly and has no separate allocation concept to
validate here.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.business_workflows.financial_engine.financial_validator import FinancialValidator
from app.business_workflows.payment.payment_workflow_service import PaymentWorkflowService


class AllocationService:
    def __init__(self, db: Session):
        self.db = db
        self.validator = FinancialValidator(db)
        self.payment_workflow = PaymentWorkflowService(db)

    def validate_allocations(self, total_amount: Decimal, allocations: list[dict]) -> None:
        self.validator.validate_allocation_sum(total_amount, allocations)

    def capture_allocated_payment(self, payment_data: dict, actor_id: Optional[int]) -> dict:
        """Validates the allocation list against the Financial Engine's
        own rule, then delegates the actual capture to the existing,
        unmodified Payment Engine — one allocation implementation, two
        entry points (the Payment Engine's own API, and this one, used
        by any Financial Engine caller that wants the extra up-front
        validation pass before attempting the capture)."""
        self.validate_allocations(payment_data["amount"], payment_data["allocations"])
        return self.payment_workflow.create_payment(payment_data, actor_id=actor_id)
