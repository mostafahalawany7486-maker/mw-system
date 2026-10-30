"""
financial_validator.py

Every VALIDATIONS rule the spec asks for. Deliberately thin: almost
every check here delegates to a query against the *existing*
Transaction table (Phase 8) or the *existing* RentalContract/
LeaseAgreement deposit fields (Phase 3/7) rather than a second,
parallel set of duplicate/refund/deposit records this module would
otherwise have to keep in sync itself — see docs/financial-engine.md's
"Conflicts found" section for why a second source of truth was
rejected outright.
"""
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.financial_repository import TransactionRepository
from app.repositories.rental_repository import RentalContractRepository
from app.repositories.lease_repository import LeaseRepository
from app.business_workflows.financial_engine.financial_exceptions import (
    DuplicateTransactionError, DuplicateDepositError, NegativeDepositError, OverRefundError,
    InvalidAllocationError, EntityNotFoundError,
)


class FinancialValidator:
    def __init__(self, db: Session):
        self.db = db
        self.txn_repo = TransactionRepository(db)
        self.rental_repo = RentalContractRepository(db)
        self.lease_repo = LeaseRepository(db)

    # ---------------- Duplicate transactions ----------------
    def validate_no_duplicate_transaction(self, reference_number: Optional[str]) -> None:
        """Spec: 'Prevent duplicate transactions.' Same check
        PaymentValidator.validate_unique_reference_number already
        performs for Payment rows — this is the transaction-level
        equivalent, since the Financial Engine's own writes go straight
        through FinancialService.create_transaction(), not through a
        Payment row."""
        if not reference_number:
            return
        existing = self.txn_repo.get_by_reference_number(reference_number)
        if existing:
            raise DuplicateTransactionError(reference_number)

    # ---------------- Security deposits ----------------
    def get_deposit_contract(self, contract_type: str, contract_id: int):
        repo = self.rental_repo if contract_type == "rental" else self.lease_repo
        contract = repo.get_detail(contract_id)
        if not contract:
            raise EntityNotFoundError("RentalContract" if contract_type == "rental" else "LeaseAgreement", contract_id)
        return contract

    def validate_can_receive_deposit(self, contract, amount: Decimal) -> None:
        if amount <= 0:
            raise NegativeDepositError()
        # Spec: 'Prevent duplicate deposits.' A contract's deposit
        # amount is a single field (Phase 3/7 design, unchanged) —
        # receiving a deposit is only valid while nothing has been
        # recorded for it yet. Once a non-zero amount is on file,
        # further deposit money for this same contract is an
        # *adjustment*, not a second "received" event.
        if contract.security_deposit_amount and contract.security_deposit_amount > 0:
            raise DuplicateDepositError(type(contract).__name__, contract.id)

    def validate_can_refund_deposit(self, contract, amount: Decimal) -> None:
        if amount <= 0:
            raise NegativeDepositError()
        available = contract.security_deposit_amount or Decimal("0")
        if amount > available:
            raise OverRefundError(str(amount), str(available))

    # ---------------- Refunds (tenant payments) ----------------
    def validate_refund_amount(self, requested: Decimal, available: Decimal) -> None:
        """Spec: 'Prevent... Over refunds.' Reused by refund_service.py
        for both a tenant payment refund (via the existing Payment
        Engine, see refund_service.py's own docstring) and a deposit
        refund above — one rule, two callers."""
        if requested <= 0:
            raise NegativeDepositError()
        if requested > available:
            raise OverRefundError(str(requested), str(available))

    # ---------------- Allocations ----------------
    def validate_allocation_sum(self, total_amount: Decimal, allocations: list) -> None:
        """Spec: 'Prevent... Invalid allocations.' Mirrors
        PaymentValidator.validate_allocations_sum_matches_amount
        exactly (Phase 16) — reused as a standalone rule here since
        allocation_service.py's owner-side allocations (recoverable
        expense -> ledger entry) don't go through the Payment Engine at
        all, so this can't just delegate to that validator directly."""
        if not allocations:
            raise InvalidAllocationError("At least one allocation is required")
        allocation_total = sum((Decimal(str(a["amount"])) for a in allocations), Decimal("0"))
        if allocation_total != total_amount:
            raise InvalidAllocationError(f"Allocations sum to {allocation_total}, which doesn't match the total amount {total_amount}")
        for a in allocations:
            if Decimal(str(a["amount"])) <= 0:
                raise InvalidAllocationError("Every allocation amount must be greater than zero")
