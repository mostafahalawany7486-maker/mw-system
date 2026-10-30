"""
Payment & Collection Engine (Phase 16).

Wraps the existing tenant-payment ledger (FinancialService.
record_invoice_payment / create_transaction, unchanged) in a two-phase
capture-then-verify lifecycle with real Refund and Reversal support —
see docs/payment-collection-engine.md for the full design write-up,
including the one architectural conflict this phase's required
analysis step found (why allocations target Invoice, not the older
Rental Receipt Module's installment/receipt) and how it was resolved.

Like rent_cycle/ (Phase 14), this is the one other sub-package under
app/business_workflows/ that owns its own SQLAlchemy models
(app/models/payment.py: Payment, PaymentAllocation) rather than being
pure orchestration — see the package-level docstring in
app/business_workflows/__init__.py for why that's a deliberate,
narrow exception.

Public entry point: PaymentWorkflowService (payment_workflow_service.py),
used directly by app/api/v1/routers/payments.py.
"""
from app.business_workflows.payment.payment_workflow_service import PaymentWorkflowService
from app.business_workflows.payment.payment_validator import PaymentValidator
from app.business_workflows.payment.payment_allocator import PaymentAllocator
from app.business_workflows.payment.payment_reversal import PaymentReversal
from app.business_workflows.payment.payment_refund import PaymentRefund
from app.business_workflows.payment.payment_exceptions import (
    PaymentError, PaymentNotFoundError, NegativePaymentAmountError, DuplicateReferenceNumberError,
    PaymentExceedsOutstandingError, PaymentOnCancelledReceiptError, InvalidPaymentStatusTransitionError,
    DuplicateReversalError, InvalidAllocationError,
)

__all__ = [
    "PaymentWorkflowService",
    "PaymentValidator",
    "PaymentAllocator",
    "PaymentReversal",
    "PaymentRefund",
    "PaymentError", "PaymentNotFoundError", "NegativePaymentAmountError", "DuplicateReferenceNumberError",
    "PaymentExceedsOutstandingError", "PaymentOnCancelledReceiptError", "InvalidPaymentStatusTransitionError",
    "DuplicateReversalError", "InvalidAllocationError",
]
