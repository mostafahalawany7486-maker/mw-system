"""
refund_service.py

Two kinds of refund the spec asks for, both reusing existing,
unmodified machinery rather than a third refund implementation:

  - A tenant PAYMENT refund (money paid against an invoice, given back)
    -> PaymentWorkflowService.refund_payment() (Phase 16) — already
    validates over-refund via PaymentValidator.
  - A SECURITY DEPOSIT refund (partial or full) -> DepositService,
    which is genuinely new (see that file's own docstring).

financial_validator.py's validate_refund_amount is the one rule shared
by both, even though they're otherwise separate code paths.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.business_workflows.payment.payment_workflow_service import PaymentWorkflowService
from app.business_workflows.financial_engine.deposit_service import DepositService


class RefundService:
    def __init__(self, db: Session):
        self.db = db
        self.payment_workflow = PaymentWorkflowService(db)
        self.deposit_service = DepositService(db)

    def refund_tenant_payment(self, payment_id: int, reason: str, actor_id: Optional[int], amount: Optional[Decimal] = None):
        return self.payment_workflow.refund_payment(payment_id, reason, actor_id=actor_id, amount=amount)

    def refund_security_deposit(self, contract_type: str, contract_id: int, amount: Decimal, account_id: int, payment_date: date, reason: Optional[str], actor_id: Optional[int], reference_number: Optional[str] = None):
        return self.deposit_service.refund_deposit(contract_type, contract_id, amount, account_id, payment_date, reason, actor_id, reference_number)
