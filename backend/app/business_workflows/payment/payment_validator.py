"""
payment_validator.py

Every business rule for what a Payment/allocation may legally do —
kept separate from payment_workflow_service.py, same "rules table
separate from orchestration" split as rent_cycle_validator.py
(Phase 14).
"""
from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.financial import InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.repositories.financial_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentRepository
from app.business_workflows.payment.payment_exceptions import (
    NegativePaymentAmountError, DuplicateReferenceNumberError, PaymentExceedsOutstandingError,
    PaymentOnCancelledReceiptError, InvalidPaymentStatusTransitionError, DuplicateReversalError,
    InvalidAllocationError,
)

# Invoices that can never receive a new allocation — matches "Payment on
# cancelled receipts" from the spec, reusing Invoice's own existing
# status vocabulary rather than inventing a parallel one.
NON_PAYABLE_INVOICE_STATUSES = {InvoiceStatus.CANCELLED, InvoiceStatus.VOID, InvoiceStatus.PAID}

VERIFIABLE_FROM = {PaymentStatus.PENDING}
CANCELLABLE_FROM = {PaymentStatus.PENDING}
REFUNDABLE_FROM = {PaymentStatus.VERIFIED, PaymentStatus.PARTIALLY_PAID, PaymentStatus.PAID}
REVERSIBLE_FROM = {PaymentStatus.VERIFIED, PaymentStatus.PARTIALLY_PAID, PaymentStatus.PAID}


class PaymentValidator:
    def __init__(self, db: Session):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.invoice_repo = InvoiceRepository(db)

    def validate_amount_positive(self, amount: Decimal) -> None:
        if amount is None or amount <= 0:
            raise NegativePaymentAmountError()

    def validate_unique_reference_number(self, reference_number: Optional[str], exclude_payment_id: Optional[int] = None) -> None:
        if not reference_number:
            return
        existing = self.payment_repo.get_by_reference_number(reference_number)
        if existing and existing.id != exclude_payment_id:
            raise DuplicateReferenceNumberError(reference_number, existing.payment_number)

    def validate_allocation_target(self, invoice, requested_amount: Decimal) -> None:
        if not invoice:
            raise InvalidAllocationError("Invalid invoice_id in allocations")
        if invoice.invoice_status in NON_PAYABLE_INVOICE_STATUSES:
            raise PaymentOnCancelledReceiptError(invoice.invoice_number, invoice.invoice_status)
        if requested_amount > invoice.outstanding_amount:
            raise PaymentExceedsOutstandingError(invoice.invoice_number, requested_amount, invoice.outstanding_amount)

    def validate_allocations_sum_matches_amount(self, amount: Decimal, allocations_in: list[dict]) -> None:
        """Domain-level backstop for the same invariant
        PaymentCreate.validate_amount_matches_allocations enforces at
        the API boundary (app/schemas/payment.py) — kept here too so a
        direct PaymentWorkflowService.create_payment() call (e.g. from
        a future script or another service) can't create a Payment
        whose amount doesn't match what it actually allocates. This is
        a data-integrity check on this module's own new entity, not a
        reimplementation of any existing money-movement rule."""
        total = sum((a["amount"] for a in allocations_in), Decimal("0"))
        if total != amount:
            raise InvalidAllocationError(f"amount ({amount}) must equal the sum of allocation amounts ({total})")

    def validate_can_verify(self, payment: Payment) -> None:
        if payment.payment_status not in VERIFIABLE_FROM:
            raise InvalidPaymentStatusTransitionError(payment.payment_status, "verify")

    def validate_can_cancel(self, payment: Payment) -> None:
        if payment.payment_status not in CANCELLABLE_FROM:
            raise InvalidPaymentStatusTransitionError(payment.payment_status, "cancel")

    def validate_can_refund(self, payment: Payment, amount: Optional[Decimal]) -> None:
        if payment.payment_status not in REFUNDABLE_FROM:
            raise InvalidPaymentStatusTransitionError(payment.payment_status, "refund")
        if amount is not None and (amount <= 0 or amount > payment.amount):
            raise InvalidAllocationError(f"Refund amount must be between 0 and the payment amount ({payment.amount})")

    def validate_can_reverse(self, payment: Payment) -> None:
        if payment.payment_status == PaymentStatus.REVERSED:
            raise DuplicateReversalError()
        if payment.payment_status not in REVERSIBLE_FROM:
            raise InvalidPaymentStatusTransitionError(payment.payment_status, "reverse")
