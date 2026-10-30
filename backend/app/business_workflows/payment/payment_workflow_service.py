"""
payment_workflow_service.py

The Payment & Collection Engine's public facade — what the API router
(app/api/v1/routers/payments.py) calls, mirroring exactly how every
other router in this codebase calls a single Service class. Internally
sequences the other modules in this package:

    PaymentValidator   -> is this action/amount/allocation allowed?
    PaymentAllocator    -> build allocations (create) / post them (verify)
    PaymentReversal     -> undo a payment that should never have posted
    PaymentRefund       -> return money for a payment that was valid

Two-phase lifecycle (see app/models/payment.py's module docstring for
why): create_payment() only captures data (status=PENDING, nothing
posted to the ledger yet); verify_payment() is the only place that
actually calls FinancialService.record_invoice_payment() and moves
money through the books. This is the new capability the spec asks for
that didn't already exist — everything downstream of "post to the
ledger" (receipt issuance, GL posting, balance updates) still happens
in exactly the same single place it always did.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.repositories.payment_repository import PaymentRepository
from app.services.audit_service import AuditService
from app.services.financial_service import FinancialService
from app.schemas.common import PaginationParams
from app.business_workflows.payment.payment_validator import PaymentValidator
from app.business_workflows.payment.payment_allocator import PaymentAllocator
from app.business_workflows.payment.payment_reversal import PaymentReversal
from app.business_workflows.payment.payment_refund import PaymentRefund
from app.business_workflows.payment.payment_exceptions import PaymentNotFoundError
from app.business_workflows.notification_workflow_service import NotificationWorkflowService

ENTITY_TYPE = "payment"


class PaymentWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PaymentRepository(db)
        self.validator = PaymentValidator(db)
        self.allocator = PaymentAllocator(db)
        self.reversal = PaymentReversal(db)
        self.refund_handler = PaymentRefund(db)
        self.audit = AuditService(db)
        self.financial_service = FinancialService(db)
        self.notification_workflow = NotificationWorkflowService(db)

    # ---------------- Lookups ----------------
    def get_payment(self, payment_id: int) -> Payment:
        payment = self.repo.get_detail(payment_id)
        if not payment:
            raise PaymentNotFoundError(payment_id)
        return payment

    def list_payments(
        self, params: PaginationParams, tenant_id: Optional[int], payment_status: Optional[str],
        payment_method: Optional[str], date_from: Optional[date], date_to: Optional[date], search: Optional[str] = None,
    ):
        return self.repo.list_payments(
            page=params.page, page_size=params.page_size, tenant_id=tenant_id, payment_status=payment_status,
            payment_method=payment_method, date_from=date_from, date_to=date_to,
            sort_by=params.sort_by, sort_dir=params.sort_dir or "desc", search=search,
        )

    # ---------------- Create (capture, no ledger effect yet) ----------------
    def create_payment(self, data: dict, actor_id: Optional[int]) -> Payment:
        self.validator.validate_amount_positive(data["amount"])
        self.validator.validate_unique_reference_number(data.get("reference_number"))
        self.validator.validate_allocations_sum_matches_amount(data["amount"], data["allocations"])

        currency = None
        account = self.financial_service.account_repo.get(data["account_id"])
        if account and account.currency_id:
            from app.repositories.organization_repository import CurrencyRepository
            currency_row = CurrencyRepository(self.db).get(account.currency_id)
            currency = currency_row.code if currency_row else None

        payment = self.repo.create({
            "payment_number": self.repo.next_payment_number(),
            "tenant_id": data["tenant_id"],
            "rental_contract_id": data.get("rental_contract_id"),
            "property_id": data.get("property_id"),
            "account_id": data["account_id"],
            "payment_method": data["payment_method"],
            "payment_date": data["payment_date"],
            "amount": data["amount"],
            "currency": currency,
            "reference_number": data.get("reference_number"),
            "notes": data.get("notes"),
            "payment_status": PaymentStatus.PENDING,
        }, actor_id=actor_id)
        self.db.flush()

        self.allocator.build_allocations(payment, data["allocations"], actor_id=actor_id)

        self.audit.log_activity(
            ENTITY_TYPE, payment.id, "created",
            f"Payment {payment.payment_number} captured: {payment.amount} via {payment.payment_method} "
            f"across {len(data['allocations'])} invoice(s)",
            actor_id,
        )
        self.audit.log_audit(ENTITY_TYPE, payment.id, "created", None, actor_id)
        self.db.commit()
        return self.get_payment(payment.id)

    # ---------------- Verify (posts to the ledger) ----------------
    def verify_payment(self, payment_id: int, actor_id: Optional[int]) -> Payment:
        payment = self.get_payment(payment_id)
        self.validator.validate_can_verify(payment)

        final_status = self.allocator.post_allocations(payment, actor_id=actor_id)
        payment.payment_status = final_status
        payment.verified_at = datetime.now(timezone.utc)
        self.db.commit()

        self.audit.log_activity(
            ENTITY_TYPE, payment.id, "verified",
            f"Payment {payment.payment_number} verified — {final_status}", actor_id,
        )
        self.audit.log_audit(ENTITY_TYPE, payment.id, "verified", {"payment_status": {"old": "pending", "new": final_status}}, actor_id)

        self.notification_workflow.notify_admins(
            title="Payment collected",
            message=f"Payment {payment.payment_number} ({payment.amount}) verified from {payment.tenant_name or 'tenant'}.",
            notification_type="success",
            entity_type=ENTITY_TYPE,
            entity_id=payment.id,
        )
        return self.get_payment(payment.id)

    # ---------------- Cancel (pending only, no ledger effect to undo) ----------------
    def cancel_payment(self, payment_id: int, reason: str, actor_id: Optional[int]) -> Payment:
        payment = self.get_payment(payment_id)
        self.validator.validate_can_cancel(payment)

        payment.payment_status = PaymentStatus.CANCELLED
        payment.cancellation_reason = reason
        self.db.commit()

        self.audit.log_activity(ENTITY_TYPE, payment.id, "cancelled", f"Payment {payment.payment_number} cancelled: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, payment.id, "cancelled", {"payment_status": {"old": "pending", "new": "cancelled"}}, actor_id)
        return self.get_payment(payment.id)

    # ---------------- Refund / Reverse ----------------
    def refund_payment(self, payment_id: int, reason: str, actor_id: Optional[int], amount: Optional[Decimal] = None) -> Payment:
        payment = self.get_payment(payment_id)
        refund_amount = amount if amount is not None else payment.amount
        self.validator.validate_can_refund(payment, amount)
        self.refund_handler.refund(payment, refund_amount, reason, actor_id=actor_id)

        self.notification_workflow.notify_admins(
            title="Payment refunded",
            message=f"Payment {payment.payment_number} refunded {refund_amount}: {reason}",
            notification_type="warning",
            entity_type=ENTITY_TYPE,
            entity_id=payment.id,
        )
        return self.get_payment(payment_id)

    def reverse_payment(self, payment_id: int, reason: str, actor_id: Optional[int]) -> Payment:
        payment = self.get_payment(payment_id)
        self.validator.validate_can_reverse(payment)
        self.reversal.reverse(payment, reason, actor_id=actor_id)

        self.notification_workflow.notify_admins(
            title="Payment reversed",
            message=f"Payment {payment.payment_number} reversed: {reason}",
            notification_type="warning",
            entity_type=ENTITY_TYPE,
            entity_id=payment.id,
        )
        return self.get_payment(payment_id)

    # ---------------- Collection Dashboard ----------------
    def dashboard(self) -> dict:
        today = date.today()
        month_start = today.replace(day=1)

        collected_today = self.repo.sum_collected_between(today, today)
        collected_this_month = self.repo.sum_collected_between(month_start, today)
        total_outstanding = self.financial_service.outstanding_balances()["total_tenant_outstanding"]
        overdue_amount = self.repo.sum_overdue_invoice_balance()

        denominator = collected_this_month + total_outstanding
        collection_percentage = (
            (collected_this_month / denominator * Decimal("100")).quantize(Decimal("0.01"))
            if denominator > 0 else Decimal("0")
        )

        return {
            "collected_today": collected_today,
            "collected_this_month": collected_this_month,
            "total_outstanding": total_outstanding,
            "overdue_amount": overdue_amount,
            "collection_percentage": collection_percentage,
            "payments_by_status": self.repo.count_by_status(),
        }
