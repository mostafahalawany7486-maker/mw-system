"""
payment_refund.py

Handles POST /payments/{id}/refund. Reuses
FinancialService.create_transaction() (transaction_type=REFUND) for the
actual money-out ledger entry and GL posting — unchanged, same as every
other module in this codebase that touches the ledger. This module's
own job is proportionally rolling back each affected invoice's
`amount_paid` (a refund undoes some or all of what was collected
against it), which — like payment_reversal.py's rollback — has no
existing equivalent to reuse; it's the genuinely new piece.

A refund is distinct from a reversal: a reversal undoes a payment that
should never have been recorded (a mistake); a refund returns money for
a payment that WAS valid but is now being given back (e.g. an
overpayment, or a tenant moving out with a credit balance). Both end up
rolling back `amount_paid`, but a refund also moves real money back out
through the ledger — a reversal does not (it un-does the original
entry, it doesn't create a new outbound one).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.financial import Invoice, InvoiceStatus, TransactionType
from app.models.payment import Payment, PaymentStatus
from app.services.financial_service import FinancialService
from app.services.audit_service import AuditService

ENTITY_TYPE = "payment"


class PaymentRefund:
    def __init__(self, db: Session):
        self.db = db
        self.financial_service = FinancialService(db)
        self.audit = AuditService(db)

    def refund(self, payment: Payment, amount: Decimal, reason: str, actor_id: Optional[int]) -> Payment:
        """Refunds `amount` (<= payment.amount), proportionally spread
        across the payment's allocations (largest allocations refunded
        first, so a partial refund of a multi-invoice payment behaves
        predictably rather than arbitrarily)."""
        remaining = amount
        ordered_allocations = sorted(payment.allocations, key=lambda a: a.amount, reverse=True)

        txn = self.financial_service.create_transaction({
            "transaction_type": TransactionType.REFUND,
            "amount": amount,
            "account_id": payment.account_id,
            "tenant_id": payment.tenant_id,
            "property_id": payment.property_id,
            "rental_contract_id": payment.rental_contract_id,
            "payment_method": payment.payment_method,
            "reference_number": payment.reference_number,
            "transaction_date": datetime.now(timezone.utc).date(),
            "description": f"Refund for payment {payment.payment_number}: {reason}",
        }, actor_id=actor_id)

        for allocation in ordered_allocations:
            if remaining <= 0:
                break
            portion = min(allocation.amount, remaining)
            invoice = self.db.get(Invoice, allocation.invoice_id)
            if invoice:
                invoice.amount_paid = max(invoice.amount_paid - portion, Decimal("0"))
                invoice.invoice_status = (
                    InvoiceStatus.PARTIALLY_PAID if invoice.amount_paid > 0 else InvoiceStatus.SENT
                )
                self.audit.log_activity(
                    "invoice", invoice.id, "refunded",
                    f"Invoice {invoice.invoice_number}: {portion} refunded (payment {payment.payment_number}, txn {txn.transaction_number})",
                    actor_id,
                )
            remaining -= portion

        payment.payment_status = PaymentStatus.REFUNDED
        payment.refund_reason = reason
        payment.refunded_at = datetime.now(timezone.utc)

        self.audit.log_activity(ENTITY_TYPE, payment.id, "refunded", f"Payment {payment.payment_number} refunded {amount}: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, payment.id, "refunded", {"payment_status": {"old": "verified", "new": "refunded"}}, actor_id)
        self.db.commit()
        return payment
