"""
owner_ledger_validator.py

Every business rule for what may be posted to the Owner Ledger — kept
separate from the services that use it, same "rules table separate
from orchestration" split as rent_cycle_validator.py (Phase 14) /
payment_validator.py (Phase 16).
"""
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.owner_repository import OwnerRepository
from app.repositories.property_repository import PropertyRepository
from app.models.owner_ledger import OwnerLedgerEntryStatus


class OwnerLedgerError(HTTPException):
    """Base class for every Owner Ledger exception — subclasses
    HTTPException directly, same pattern as every other business
    workflow exception module in this codebase."""


class OwnerNotFoundError(OwnerLedgerError):
    def __init__(self, owner_id: int):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid owner_id: {owner_id}")


class InvalidPropertyForOwnerError(OwnerLedgerError):
    def __init__(self, property_id: int, owner_id: int):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Property {property_id} does not belong to owner {owner_id}",
        )


class NegativeAmountError(OwnerLedgerError):
    def __init__(self):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be greater than zero")


class EntryNotFoundError(OwnerLedgerError):
    def __init__(self, entry_id: int):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Owner ledger entry {entry_id} not found")


class AlreadyReversedError(OwnerLedgerError):
    def __init__(self, entry_id: int):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=f"Ledger entry {entry_id} has already been reversed")


class CannotReverseAReversalError(OwnerLedgerError):
    def __init__(self, entry_id: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ledger entry {entry_id} is itself a reversal entry and cannot be reversed again "
                   f"(post a new correcting entry instead)",
        )


class OwnerLedgerValidator:
    def __init__(self, db: Session):
        self.db = db
        self.owner_repo = OwnerRepository(db)
        self.property_repo = PropertyRepository(db)

    def validate_owner(self, owner_id: int):
        owner = self.owner_repo.get(owner_id)
        if not owner:
            raise OwnerNotFoundError(owner_id)
        return owner

    def validate_property_belongs_to_owner(self, property_id: Optional[int], owner_id: int):
        if property_id is None:
            return
        property_ = self.property_repo.get(property_id)
        if not property_ or property_.owner_id != owner_id:
            raise InvalidPropertyForOwnerError(property_id, owner_id)

    def validate_amount_positive(self, amount: Decimal):
        if amount is None or amount <= 0:
            raise NegativeAmountError()

    def validate_single_sided(self, debit: Decimal, credit: Decimal):
        """A ledger entry affects exactly one side — never both, never
        neither. Matches standard double-entry-adjacent sub-ledger
        convention (see app/models/owner_ledger.py's docstring)."""
        debit = debit or Decimal("0")
        credit = credit or Decimal("0")
        if debit < 0 or credit < 0:
            raise NegativeAmountError()
        if debit > 0 and credit > 0:
            raise OwnerLedgerError(status_code=status.HTTP_400_BAD_REQUEST, detail="An entry cannot have both a debit and a credit — post two entries instead")
        if debit == 0 and credit == 0:
            raise OwnerLedgerError(status_code=status.HTTP_400_BAD_REQUEST, detail="An entry must have a non-zero debit or credit")

    def validate_can_reverse(self, entry) -> None:
        if entry.entry_status == OwnerLedgerEntryStatus.REVERSED:
            raise AlreadyReversedError(entry.id)
        if entry.entry_status == OwnerLedgerEntryStatus.REVERSAL:
            raise CannotReverseAReversalError(entry.id)
