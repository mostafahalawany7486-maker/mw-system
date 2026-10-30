"""
payment_allocator.py

Everything about *which* invoices a Payment's amount is split across —
this is what makes "one payment covering multiple receipts" (per spec)
possible. Two responsibilities, corresponding to Payment's two phases:

  build_allocations()  — at create_payment() time: validates every
                          requested allocation and creates the
                          PaymentAllocation rows. No money moves yet.
  post_allocations()   — at verify_payment() time: for each allocation,
                          calls the EXISTING, unmodified
                          FinancialService.record_invoice_payment() —
                          which already does partial-payment accounting,
                          receipt auto-issuance, and GL posting
                          correctly. This module never reimplements any
                          of that; it only decides how to split the
                          Payment's total across invoices and derives
                          the resulting overall Payment status from
                          each invoice's own (already correct)
                          post-payment status.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentAllocation, PaymentStatus
from app.models.financial import InvoiceStatus
from app.repositories.financial_repository import InvoiceRepository
from app.repositories.payment_repository import PaymentAllocationRepository
from app.services.financial_service import FinancialService
from app.business_workflows.payment.payment_validator import PaymentValidator


class PaymentAllocator:
    def __init__(self, db: Session):
        self.db = db
        self.invoice_repo = InvoiceRepository(db)
        self.allocation_repo = PaymentAllocationRepository(db)
        self.financial_service = FinancialService(db)
        self.validator = PaymentValidator(db)

    def build_allocations(self, payment: Payment, allocations_in: list[dict], actor_id: Optional[int]) -> list[PaymentAllocation]:
        """Validates and creates one PaymentAllocation row per requested
        (invoice_id, amount) pair. Purely a data-capture step — no
        Transaction is created here."""
        created = []
        for entry in allocations_in:
            invoice = self.invoice_repo.get(entry["invoice_id"])
            self.validator.validate_allocation_target(invoice, entry["amount"])
            allocation = self.allocation_repo.create({
                "payment_id": payment.id,
                "invoice_id": entry["invoice_id"],
                "amount": entry["amount"],
            }, actor_id=actor_id)
            created.append(allocation)
        return created

    def post_allocations(self, payment: Payment, actor_id: Optional[int]) -> str:
        """Posts every allocation to the ledger via the existing
        FinancialService.record_invoice_payment() and returns the
        overall Payment status that follows from the result:
        PAID if every allocated invoice is now fully paid,
        PARTIALLY_PAID if at least one still has an outstanding balance.

        Re-validates each allocation's target against its CURRENT
        outstanding balance (not just what it was at create_payment
        time) — the same defense-in-depth
        FinancialService.record_invoice_payment already applies on its
        own amount parameter, just surfaced earlier with a clearer
        Payment-specific error.
        """
        all_fully_paid = True
        for allocation in payment.allocations:
            invoice = self.invoice_repo.get(allocation.invoice_id)
            self.validator.validate_allocation_target(invoice, allocation.amount)

            updated_invoice = self.financial_service.record_invoice_payment(
                allocation.invoice_id, payment.account_id, payment.payment_method, payment.reference_number,
                payment.payment_date, actor_id=actor_id, amount=allocation.amount,
            )
            allocation.transaction_id = updated_invoice.paid_transaction_id
            if updated_invoice.invoice_status != InvoiceStatus.PAID:
                all_fully_paid = False

        return PaymentStatus.PAID if all_fully_paid else PaymentStatus.PARTIALLY_PAID
