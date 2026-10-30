"""
owner_settlement_service.py

IMPORTANT — naming/scope note (see docs/owner-ledger-engine.md for the
full write-up): this is NOT a replacement for the existing
`OwnerSettlementWorkflowService` (Phase 12,
app/business_workflows/owner_settlement_workflow_service.py), which
already pays out Owner <-> Company lease installments correctly and is
left completely untouched. This class is named differently
(`OwnerLedgerSettlementService`, not `OwnerSettlementWorkflowService`)
specifically to avoid the kind of duplicate-capability collision two
earlier phases each had to retire an older module over (see
app/business_workflows/__init__.py's docstring). This one does not
reimplement settlement — it *delegates* to the existing service for
the actual payout, and its only additional job is mirroring that event
into the new Owner Ledger (an "Owner Payment" debit entry), which the
Phase 12 service has no reason to know about and was not modified to
produce, since the spec instructs modifying existing modules only when
absolutely required — this integration was achievable without doing so.

No new API endpoint calls this directly in this phase (the spec's own
requested API surface for Owner Ledger doesn't include one) — it's the
integration point a caller (a future endpoint, or an admin script) uses
when it wants an owner lease settlement reflected in the Owner
Statement. Calling the bare Phase 12 service directly still works
exactly as before; it simply won't show up on an Owner Statement.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.owner_ledger import OwnerLedgerTransactionType
from app.business_workflows.owner_settlement_workflow_service import OwnerSettlementWorkflowService
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService


class OwnerLedgerSettlementService:
    def __init__(self, db: Session):
        self.db = db
        self.settlement = OwnerSettlementWorkflowService(db)
        self.ledger = OwnerLedgerService(db)

    def pay_owner_balance(
        self, owner_id: int, amount: Decimal, account_id: int, transaction_date: date, actor_id: Optional[int],
        payment_method: Optional[str] = None, reference_number: Optional[str] = None,
    ) -> dict:
        """General-purpose owner settlement: pays down the owner's
        current Owner Ledger balance directly (their accumulated
        rental income, not tied to any one Lease installment) — for
        the common case where rent was recorded as Rental Income on
        the ledger (a Manual Entry, or from a source other than a
        Master Lease installment) and now needs to actually be paid
        out. Creates the real Transaction (a receipt is generated,
        same as any other owner_payment) and posts the matching debit
        to the Owner Ledger in the same call, exactly like
        settle_and_record() does for a specific installment — this is
        the same idea, just not anchored to one.
        """
        from app.services.financial_service import FinancialService

        if amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount must be greater than zero")

        owner = self.ledger.validator.validate_owner(owner_id)
        current_balance = self.ledger.repo.get_last_entry(owner_id)
        current_balance = current_balance.balance if current_balance else Decimal("0")
        if amount > current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Amount ({amount}) exceeds this owner's current outstanding balance ({current_balance})",
            )

        # Raised directly: "Profit by Property" (and the Dashboard's own
        # per-property profit) was showing 0 expense for a building even
        # after paying its owner — because a general balance payment
        # (not anchored to one specific lease installment, unlike
        # settle_and_record() below) never set property_id on the
        # Transaction it created, so nothing tied it back to a property
        # for those reports to attribute it to. Fixed for the common,
        # unambiguous case: if this owner has exactly one property,
        # attribute the payment to it automatically. An owner with
        # several properties has no single correct property to guess at
        # for a balance that may span all of them — left unattributed
        # there rather than guessing wrong, same as before.
        from app.models.property import Property as PropertyModel
        owner_properties = self.db.query(PropertyModel.id).filter(
            PropertyModel.owner_id == owner_id, PropertyModel.deleted_at.is_(None), PropertyModel.parent_property_id.is_(None),
        ).all()
        single_property_id = owner_properties[0][0] if len(owner_properties) == 1 else None

        txn = FinancialService(self.db).create_transaction({
            "transaction_type": "owner_payment",
            "amount": amount,
            "account_id": account_id,
            "owner_id": owner_id,
            "property_id": single_property_id,
            "payment_method": payment_method,
            "reference_number": reference_number,
            "transaction_date": transaction_date,
            "description": f"Owner payment to {owner.display_name} — settles outstanding Owner Ledger balance",
        }, actor_id=actor_id)

        entry = self.ledger.post_entry(
            owner_id=owner_id, transaction_date=transaction_date, transaction_type=OwnerLedgerTransactionType.OWNER_PAYMENT,
            description=f"Owner payment — transaction {txn.transaction_number}", actor_id=actor_id,
            debit=amount, reference_type="transaction", reference_id=txn.id,
        )
        # A Receipt is auto-issued for owner_payment transactions inside
        # create_transaction() (RECEIPT_ELIGIBLE_TYPES) — refreshed here
        # so its id can be handed back for the printable/signable receipt.
        self.db.refresh(txn)
        receipt_id = txn.receipt.id if txn.receipt else None
        return {
            "transaction_id": txn.id, "transaction_number": txn.transaction_number,
            "ledger_entry": entry, "new_balance": entry.balance, "receipt_id": receipt_id,
        }

    def settle_and_record(
        self, lease_id: int, installment_id: int, account_id: int, transaction_date: date, actor_id: Optional[int],
        payment_method: Optional[str] = None, reference_number: Optional[str] = None,
    ) -> dict:
        """Settles one owner lease installment (via the existing,
        unmodified Phase 12 flow) and mirrors it into the Owner Ledger
        as a debit (an Owner Payment reduces what the company owes the
        owner)."""
        lease = self.settlement.lease_service.get_lease(lease_id)
        installment = next((i for i in lease.installments if i.id == installment_id), None)
        amount = installment.amount if installment else Decimal("0")
        installment_number = installment.installment_number if installment else None

        result = self.settlement.settle_owner_installment(
            lease_id, installment_id, account_id, transaction_date, actor_id=actor_id,
            payment_method=payment_method, reference_number=reference_number,
        )

        entry = self.ledger.post_entry(
            owner_id=lease.owner_id,
            transaction_date=transaction_date,
            transaction_type=OwnerLedgerTransactionType.OWNER_PAYMENT,
            description=f"Owner payment — lease {lease.contract_number}, installment #{installment_number}",
            actor_id=actor_id,
            debit=amount,
            credit=Decimal("0"),
            property_id=lease.property_id,
            reference_type="lease_payment_installment",
            reference_id=installment_id,
        )
        # settle_owner_installment (Phase 12) doesn't return the
        # Transaction it created directly (its WorkflowResult.data is
        # the LeaseAgreement) — looked up the same way instead, via the
        # installment link every such transaction has.
        from app.models.financial import Transaction, TransactionType
        txn = (
            self.db.query(Transaction)
            .filter(Transaction.lease_installment_id == installment_id, Transaction.transaction_type == TransactionType.OWNER_PAYMENT)
            .order_by(Transaction.id.desc())
            .first()
        )
        receipt_id = txn.receipt.id if txn and txn.receipt else None
        return {"settlement_result": result, "ledger_entry": entry, "receipt_id": receipt_id}
