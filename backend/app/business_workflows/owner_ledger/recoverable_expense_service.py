"""
recoverable_expense_service.py

Implements the spec's core business rules verbatim:

  "When company pays: Create Recoverable Expense, Increase Owner
   Outstanding Balance."
  "When owner reimburses company: Create Recovered Amount, Reduce
   Outstanding Balance."
  "Never classify recoverable expenses as company operating expenses."

Money still moves through the real ledger — both methods call
FinancialService.create_transaction() unchanged, which still triggers
GL auto-posting, exactly like every other payment path in this
codebase — but with the new RECOVERABLE_EXPENSE / OWNER_REIMBURSEMENT
transaction types (app/models/financial.py) instead of EXPENSE/INCOME,
which is what keeps these out of company operating-expense reporting.
The corresponding OwnerLedgerEntry (via OwnerLedgerService.post_entry)
is what actually tracks the owner's recoverable balance; the
Transaction is the cash-movement record, same division of
responsibility as everywhere else in this codebase (Payment ->
Transaction, RentCycle -> Invoice, etc.).
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.financial import TransactionType
from app.models.owner_ledger import OwnerLedgerTransactionType
from app.services.financial_service import FinancialService
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService
from app.business_workflows.owner_ledger.owner_ledger_validator import OwnerLedgerValidator


class RecoverableExpenseService:
    def __init__(self, db: Session):
        self.db = db
        self.financial_service = FinancialService(db)
        self.ledger = OwnerLedgerService(db)
        self.validator = OwnerLedgerValidator(db)

    def create_recoverable_expense(
        self,
        owner_id: int,
        account_id: int,
        amount: Decimal,
        expense_category: str,
        description: str,
        payment_date: date,
        actor_id: Optional[int],
        property_id: Optional[int] = None,
        reference_number: Optional[str] = None,
    ) -> dict:
        """The company pays a third party (municipality, utility,
        contractor, insurer, ...) on the owner's behalf. Returns both
        the underlying Transaction and the resulting OwnerLedgerEntry.
        """
        self.validator.validate_owner(owner_id)
        self.validator.validate_property_belongs_to_owner(property_id, owner_id)
        self.validator.validate_amount_positive(amount)

        txn = self.financial_service.create_transaction({
            "transaction_type": TransactionType.RECOVERABLE_EXPENSE,
            "amount": amount,
            "account_id": account_id,
            "owner_id": owner_id,
            "property_id": property_id,
            "category": expense_category,
            "reference_number": reference_number,
            "transaction_date": payment_date,
            "description": f"Recoverable expense ({expense_category}) on behalf of owner {owner_id}: {description}",
        }, actor_id=actor_id)

        entry = self.ledger.post_entry(
            owner_id=owner_id,
            transaction_date=payment_date,
            transaction_type=OwnerLedgerTransactionType.RECOVERABLE_EXPENSE,
            description=description,
            actor_id=actor_id,
            debit=amount,
            credit=Decimal("0"),
            property_id=property_id,
            expense_category=expense_category,
            reference_type="transaction",
            reference_id=txn.id,
        )
        return {"transaction": txn, "ledger_entry": entry}

    def record_recovered_payment(
        self,
        owner_id: int,
        account_id: int,
        amount: Decimal,
        payment_method: str,
        payment_date: date,
        actor_id: Optional[int],
        property_id: Optional[int] = None,
        reference_number: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """The owner reimburses the company for previously paid
        recoverable expenses."""
        self.validator.validate_owner(owner_id)
        self.validator.validate_property_belongs_to_owner(property_id, owner_id)
        self.validator.validate_amount_positive(amount)

        txn = self.financial_service.create_transaction({
            "transaction_type": TransactionType.OWNER_REIMBURSEMENT,
            "amount": amount,
            "account_id": account_id,
            "owner_id": owner_id,
            "property_id": property_id,
            "payment_method": payment_method,
            "reference_number": reference_number,
            "transaction_date": payment_date,
            "description": notes or f"Owner reimbursement from owner {owner_id}",
        }, actor_id=actor_id)

        entry = self.ledger.post_entry(
            owner_id=owner_id,
            transaction_date=payment_date,
            transaction_type=OwnerLedgerTransactionType.RECOVERED_AMOUNT,
            description=notes or "Recoverable expense reimbursement",
            actor_id=actor_id,
            debit=Decimal("0"),
            credit=amount,
            property_id=property_id,
            reference_type="transaction",
            reference_id=txn.id,
        )
        return {"transaction": txn, "ledger_entry": entry}
