"""
payment_reversal.py

Handles POST /payments/{id}/reverse. A posted financial transaction is
never deleted (see FinancialService.delete_transaction's own existing
guard: it refuses to delete a transaction with a posted journal entry)
— it is *reversed*, via the existing, unmodified
JournalEntryService.reverse_entry(), which creates a proper mirror-image
reversing journal entry and marks the original entry REVERSED. This
module's only new responsibility is finding the right journal entry to
reverse for each of a Payment's allocations, and rolling back the
Invoice-side `amount_paid`/`invoice_status` bookkeeping that reversing
a posted transaction implies (record_invoice_payment has no "undo" of
its own — that gap is exactly what this module fills, and it is the
one piece of genuinely new business logic in this module, not a
reimplementation of anything that already existed).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial import Invoice, InvoiceStatus
from app.models.accounting import JournalEntry, EntryStatus
from app.models.payment import Payment, PaymentStatus
from app.services.accounting_service import JournalEntryService
from app.services.audit_service import AuditService

ENTITY_TYPE = "payment"


class PaymentReversal:
    def __init__(self, db: Session):
        self.db = db
        self.journal_service = JournalEntryService(db)
        self.audit = AuditService(db)

    def _find_posted_entry_for_transaction(self, transaction_id: int) -> Optional[JournalEntry]:
        stmt = select(JournalEntry).where(
            JournalEntry.source_transaction_id == transaction_id,
            JournalEntry.entry_status == EntryStatus.POSTED,
            JournalEntry.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def reverse(self, payment: Payment, reason: str, actor_id: Optional[int]) -> Payment:
        for allocation in payment.allocations:
            if not allocation.transaction_id:
                continue  # never actually posted (e.g. a stale/failed allocation) — nothing to reverse

            entry = self._find_posted_entry_for_transaction(allocation.transaction_id)
            if entry:
                self.journal_service.reverse_entry(entry.id, reversal_date=payment.payment_date, actor_id=actor_id)

            invoice = self.db.get(Invoice, allocation.invoice_id)
            if invoice:
                invoice.amount_paid = max(invoice.amount_paid - allocation.amount, Decimal("0"))
                invoice.invoice_status = (
                    InvoiceStatus.PARTIALLY_PAID if invoice.amount_paid > 0 else InvoiceStatus.SENT
                )
                self.audit.log_activity(
                    "invoice", invoice.id, "payment_reversed",
                    f"Invoice {invoice.invoice_number}: {allocation.amount} un-applied "
                    f"(payment {payment.payment_number} reversed)",
                    actor_id,
                )

        payment.payment_status = PaymentStatus.REVERSED
        payment.reversed_at = datetime.now(timezone.utc)
        payment.notes = f"{payment.notes}\nReversed: {reason}" if payment.notes else f"Reversed: {reason}"

        self.audit.log_activity(ENTITY_TYPE, payment.id, "reversed", f"Payment {payment.payment_number} reversed: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, payment.id, "reversed", {"payment_status": {"old": "verified", "new": "reversed"}}, actor_id)
        self.db.commit()
        return payment
