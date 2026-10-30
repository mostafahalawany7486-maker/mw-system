"""
adjustment_service.py

"Manual Correction"/"Adjustment" from the spec's transaction type list.

Owner-side: reuses OwnerLedgerService.post_entry() with
transaction_type=ADJUSTMENT (Phase 17, unchanged) — an owner adjustment
is already a first-class concept there.

Tenant-side: there is no equivalent "tenant ledger" table to post an
adjustment entry into (see balance_service.py's module docstring — the
Tenant Ledger is a live view over Transaction + RentalPaymentInstallment,
not a table of its own). A tenant adjustment is therefore recorded as a
plain Transaction (transaction_type=ADJUSTMENT, a new additive
TransactionType value — see app/models/financial.py; tenant_id set) —
visible on that tenant's ledger view and in the transaction list, but
deliberately NOT written back onto any RentalPaymentInstallment row,
since silently rewriting an installment's amount is exactly the kind of
"modify a completed module" this phase is told to avoid. A large/
recurring need for real credit-note-style adjustments against specific
installments would be a reasonable ask for the Rent Billing Engine
itself in a future phase, not something to retrofit here.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.financial import TransactionType
from app.models.owner_ledger import OwnerLedgerTransactionType
from app.business_workflows.financial_engine.financial_transaction_service import FinancialTransactionService
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService


class AdjustmentService:
    def __init__(self, db: Session):
        self.db = db
        self.txn_service = FinancialTransactionService(db)
        self.owner_ledger = OwnerLedgerService(db)

    def adjust_owner_balance(self, owner_id: int, amount: Decimal, description: str, actor_id: Optional[int], is_credit: bool = True, property_id: Optional[int] = None, adjustment_date: Optional[date] = None):
        return self.owner_ledger.post_entry(
            owner_id=owner_id, transaction_date=adjustment_date or date.today(), transaction_type=OwnerLedgerTransactionType.ADJUSTMENT,
            description=description, actor_id=actor_id, credit=amount if is_credit else Decimal("0"),
            debit=Decimal("0") if is_credit else amount, property_id=property_id,
        )

    def adjust_tenant_balance(self, tenant_id: int, account_id: int, amount: Decimal, description: str, actor_id: Optional[int], adjustment_date: Optional[date] = None, property_id: Optional[int] = None):
        return self.txn_service.record(
            transaction_type=TransactionType.ADJUSTMENT, amount=amount, account_id=account_id,
            transaction_date=adjustment_date or date.today(), actor_id=actor_id,
            tenant_id=tenant_id, property_id=property_id, description=description,
        )
