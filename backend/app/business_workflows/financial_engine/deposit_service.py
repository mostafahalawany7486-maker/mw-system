"""
deposit_service.py

The full Security Deposit lifecycle the spec asks for: Received, Held
(the resting state between actions, not an action itself), Partial
Refund, Full Refund, Deduction, Forfeit, Transfer to Owner. Works for
both RentalContract (tenant deposit) and LeaseAgreement (owner deposit)
— see DepositContractType.

Every action that involves real cash movement creates a real
Transaction via the existing, unmodified
FinancialService.create_transaction() (so GL auto-posting, receipts,
and everything else already wired to a Transaction keeps working
unchanged) and appends one DepositLedgerEntry recording the running
remaining balance. A Deduction is the one action that does NOT create a
new Transaction: the cash was already received and is already sitting
in a company account from the original RECEIVED transaction — a
deduction just reduces how much of it is still owed back to the
tenant/owner, which is a bookkeeping fact, not a new cash movement.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.financial import TransactionType
from app.models.financial_engine import DepositAction, DepositContractType
from app.models.rental import RentalSecurityDepositStatus
from app.services.financial_service import FinancialService
from app.repositories.deposit_repository import DepositLedgerRepository
from app.business_workflows.financial_engine.financial_validator import FinancialValidator
from app.business_workflows.financial_engine.financial_exceptions import (
    InvalidDepositTransitionError, NegativeDepositError, OverRefundError,
)
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService
from app.models.owner_ledger import OwnerLedgerTransactionType


class DepositService:
    def __init__(self, db: Session):
        self.db = db
        self.financial_service = FinancialService(db)
        self.ledger_repo = DepositLedgerRepository(db)
        self.validator = FinancialValidator(db)

    def _contract_link_fields(self, contract_type: str, contract) -> dict:
        if contract_type == DepositContractType.RENTAL:
            return {"tenant_id": contract.tenant_id, "rental_contract_id": contract.id}
        return {"owner_id": contract.owner_id, "lease_agreement_id": contract.id}

    def _remaining_balance(self, contract_type: str, contract_id: int) -> Decimal:
        last = self.ledger_repo.get_last_entry(contract_type, contract_id)
        return last.balance_after if last else Decimal("0")

    def get_summary(self, contract_type: str, contract_id: int) -> dict:
        contract = self.validator.get_deposit_contract(contract_type, contract_id)
        entries = self.ledger_repo.list_for_contract(contract_type, contract_id)
        return {
            "contract_type": contract_type,
            "contract_id": contract_id,
            "original_amount": contract.security_deposit_amount,
            "remaining_balance": self._remaining_balance(contract_type, contract_id),
            "status": contract.security_deposit_status,
            "entries": entries,
        }

    # ---------------- Received ----------------
    def receive_deposit(self, contract_type: str, contract_id: int, amount: Decimal, account_id: int, payment_date: date, actor_id: Optional[int], reference_number: Optional[str] = None) -> dict:
        contract = self.validator.get_deposit_contract(contract_type, contract_id)
        self.validator.validate_can_receive_deposit(contract, amount)
        self.validator.validate_no_duplicate_transaction(reference_number)

        txn = self.financial_service.create_transaction({
            "transaction_type": TransactionType.DEPOSIT_RECEIVED,
            "amount": amount, "account_id": account_id, "transaction_date": payment_date,
            "reference_number": reference_number,
            "description": f"Security deposit received ({contract_type} #{contract_id})",
            **self._contract_link_fields(contract_type, contract),
        }, actor_id=actor_id)

        contract.security_deposit_amount = amount
        contract.security_deposit_status = RentalSecurityDepositStatus.HELD
        self.db.commit()

        entry = self.ledger_repo.create({
            "contract_type": contract_type, "contract_id": contract_id, "action": DepositAction.RECEIVED,
            "amount": amount, "balance_after": amount, "transaction_id": txn.id, "reference_number": reference_number,
        }, actor_id=actor_id)
        self.db.commit()
        return {"transaction": txn, "ledger_entry": entry}

    # ---------------- Refund (partial or full) ----------------
    def refund_deposit(self, contract_type: str, contract_id: int, amount: Decimal, account_id: int, payment_date: date, reason: Optional[str], actor_id: Optional[int], reference_number: Optional[str] = None) -> dict:
        contract = self.validator.get_deposit_contract(contract_type, contract_id)
        if contract.security_deposit_status in (RentalSecurityDepositStatus.RETURNED, RentalSecurityDepositStatus.FORFEITED):
            raise InvalidDepositTransitionError(contract.security_deposit_status, "refund")

        remaining = self._remaining_balance(contract_type, contract_id)
        self.validator.validate_refund_amount(amount, remaining)

        txn = self.financial_service.create_transaction({
            "transaction_type": TransactionType.DEPOSIT_REFUND,
            "amount": amount, "account_id": account_id, "transaction_date": payment_date,
            "reference_number": reference_number, "description": reason or f"Security deposit refund ({contract_type} #{contract_id})",
            **self._contract_link_fields(contract_type, contract),
        }, actor_id=actor_id)

        new_balance = remaining - amount
        is_full = new_balance <= 0
        contract.security_deposit_status = RentalSecurityDepositStatus.RETURNED if is_full else RentalSecurityDepositStatus.PARTIALLY_RETURNED
        self.db.commit()

        entry = self.ledger_repo.create({
            "contract_type": contract_type, "contract_id": contract_id,
            "action": DepositAction.FULL_REFUND if is_full else DepositAction.PARTIAL_REFUND,
            "amount": amount, "balance_after": max(new_balance, Decimal("0")), "reason": reason,
            "transaction_id": txn.id, "reference_number": reference_number,
        }, actor_id=actor_id)
        self.db.commit()
        return {"transaction": txn, "ledger_entry": entry}

    # ---------------- Deduction (damages, kept by company — no new cash movement) ----------------
    def deduct_deposit(self, contract_type: str, contract_id: int, amount: Decimal, reason: str, actor_id: Optional[int]) -> dict:
        contract = self.validator.get_deposit_contract(contract_type, contract_id)
        if contract.security_deposit_status in (RentalSecurityDepositStatus.RETURNED, RentalSecurityDepositStatus.FORFEITED):
            raise InvalidDepositTransitionError(contract.security_deposit_status, "deduct from")
        remaining = self._remaining_balance(contract_type, contract_id)
        if amount <= 0:
            raise NegativeDepositError()
        if amount > remaining:
            raise OverRefundError(str(amount), str(remaining))

        new_balance = remaining - amount
        contract.security_deposit_status = RentalSecurityDepositStatus.PARTIALLY_RETURNED if new_balance > 0 else RentalSecurityDepositStatus.FORFEITED
        self.db.commit()

        entry = self.ledger_repo.create({
            "contract_type": contract_type, "contract_id": contract_id, "action": DepositAction.DEDUCTION,
            "amount": amount, "balance_after": new_balance, "reason": reason,
        }, actor_id=actor_id)
        self.db.commit()
        return {"ledger_entry": entry}

    # ---------------- Forfeit (entire remaining balance) ----------------
    def forfeit_deposit(self, contract_type: str, contract_id: int, reason: str, actor_id: Optional[int]) -> dict:
        contract = self.validator.get_deposit_contract(contract_type, contract_id)
        if contract.security_deposit_status in (RentalSecurityDepositStatus.RETURNED, RentalSecurityDepositStatus.FORFEITED):
            raise InvalidDepositTransitionError(contract.security_deposit_status, "forfeit")
        remaining = self._remaining_balance(contract_type, contract_id)

        contract.security_deposit_status = RentalSecurityDepositStatus.FORFEITED
        self.db.commit()

        entry = self.ledger_repo.create({
            "contract_type": contract_type, "contract_id": contract_id, "action": DepositAction.FORFEIT,
            "amount": remaining, "balance_after": Decimal("0"), "reason": reason,
        }, actor_id=actor_id)
        self.db.commit()
        return {"ledger_entry": entry}

    # ---------------- Transfer to owner ----------------
    def transfer_to_owner(self, contract_type: str, contract_id: int, amount: Decimal, owner_id: int, actor_id: Optional[int], reason: Optional[str] = None) -> dict:
        """Only meaningful for a tenant (RentalContract) deposit — moving
        some or all of a forfeited/deducted tenant deposit to the
        property owner. Reuses OwnerLedgerService.post_entry (Phase 17,
        unchanged) rather than inventing a second owner-balance
        mechanism — this shows up on that same owner's existing Owner
        Ledger tab as an OWNER_PAYMENT credit."""
        contract = self.validator.get_deposit_contract(contract_type, contract_id)
        remaining = self._remaining_balance(contract_type, contract_id)
        if amount <= 0:
            raise NegativeDepositError()
        if amount > remaining:
            raise OverRefundError(str(amount), str(remaining))

        owner_ledger = OwnerLedgerService(self.db)
        ledger_entry = owner_ledger.post_entry(
            owner_id=owner_id, transaction_date=date.today(), transaction_type=OwnerLedgerTransactionType.OWNER_PAYMENT,
            description=reason or f"Security deposit transfer ({contract_type} #{contract_id})",
            actor_id=actor_id, credit=amount, property_id=getattr(contract, "property_id", None),
            reference_type="deposit_ledger", reference_id=contract_id,
        )

        new_balance = remaining - amount
        entry = self.ledger_repo.create({
            "contract_type": contract_type, "contract_id": contract_id, "action": DepositAction.TRANSFER_TO_OWNER,
            "amount": amount, "balance_after": new_balance, "reason": reason,
        }, actor_id=actor_id)
        self.db.commit()
        return {"owner_ledger_entry": ledger_entry, "deposit_ledger_entry": entry}
