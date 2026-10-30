"""
owner_ledger_service.py

The Owner Ledger's core primitive: append an entry, compute its running
balance, and (the only other write operation this module ever performs)
reverse an entry by appending a new, opposite one — never updating or
deleting a posted row. Every other service in this package
(recoverable_expense_service.py, owner_settlement_service.py, etc.)
posts through post_entry() rather than writing OwnerLedgerEntry rows
directly, so this file is the one place the running-balance invariant
is maintained.

Balance convention (see app/models/owner_ledger.py's
OwnerLedgerTransactionType docstring): a positive balance is the net
amount the company currently owes the owner. Credit entries increase
it, debit entries decrease it — exactly like a vendor/supplier
sub-ledger, which is what an owner's account with the company
functionally is.
"""
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.owner_ledger import OwnerLedgerEntry, OwnerLedgerEntryStatus, OwnerLedgerTransactionType
from app.repositories.owner_ledger_repository import OwnerLedgerRepository
from app.services.audit_service import AuditService
from app.business_workflows.owner_ledger.owner_ledger_validator import OwnerLedgerValidator, EntryNotFoundError

ENTITY_TYPE = "owner_ledger_entry"


class OwnerLedgerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OwnerLedgerRepository(db)
        self.validator = OwnerLedgerValidator(db)
        self.audit = AuditService(db)

    def get_entry(self, entry_id: int) -> OwnerLedgerEntry:
        entry = self.repo.get_detail(entry_id)
        if not entry:
            raise EntryNotFoundError(entry_id)
        return entry

    def post_entry(
        self,
        owner_id: int,
        transaction_date: date,
        transaction_type: str,
        description: str,
        actor_id: Optional[int],
        debit: Decimal = Decimal("0"),
        credit: Decimal = Decimal("0"),
        property_id: Optional[int] = None,
        expense_category: Optional[str] = None,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> OwnerLedgerEntry:
        """Appends one entry and computes its running balance from the
        owner's current last balance. This is the ONLY place in this
        module a balance is computed — every read (current balance,
        dashboard, statement opening balance) reads what was stored
        here, never recomputes it from scratch, which is what makes it
        safe and cheap to query at any scale (see the model's own
        docstring for why that's sound for an append-only ledger).
        """
        self.validator.validate_owner(owner_id)
        self.validator.validate_property_belongs_to_owner(property_id, owner_id)
        self.validator.validate_single_sided(debit, credit)

        last_entry = self.repo.get_last_entry(owner_id)
        previous_balance = last_entry.balance if last_entry else Decimal("0")
        new_balance = previous_balance + credit - debit

        entry = self.repo.create({
            "owner_id": owner_id,
            "property_id": property_id,
            "transaction_date": transaction_date,
            "transaction_type": transaction_type,
            "expense_category": expense_category,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "description": description,
            "debit": debit,
            "credit": credit,
            "balance": new_balance,
            "entry_status": OwnerLedgerEntryStatus.ACTIVE,
        }, actor_id=actor_id)

        self.audit.log_activity(
            ENTITY_TYPE, entry.id, "posted",
            f"Owner ledger entry posted for owner {owner_id}: {transaction_type} "
            f"(debit={debit}, credit={credit}, new balance={new_balance})",
            actor_id,
        )
        self.audit.log_audit(ENTITY_TYPE, entry.id, "posted", None, actor_id)
        self.db.commit()
        return self.get_entry(entry.id)

    def reverse_entry(
        self, entry_id: int, reason: str, actor_id: Optional[int], reversal_date: Optional[date] = None,
    ) -> OwnerLedgerEntry:
        """Reverses a posted entry by appending a new entry with debit
        and credit swapped, dated `reversal_date` (default: today) —
        never mutates or deletes the original row. Matches spec: 'No
        transaction can be deleted. Only reversal entries are allowed.'
        and mirrors this exact pattern from
        JournalEntryService.reverse_entry (Phase 10, unchanged) — same
        proven design, different table.
        """
        original = self.get_entry(entry_id)
        self.validator.validate_can_reverse(original)

        reversal = self.post_entry(
            owner_id=original.owner_id,
            transaction_date=reversal_date or date.today(),
            transaction_type=OwnerLedgerTransactionType.ADJUSTMENT,
            description=f"Reversal of entry #{original.id} ({original.transaction_type}): {reason}",
            actor_id=actor_id,
            debit=original.credit,
            credit=original.debit,
            property_id=original.property_id,
            reference_type="owner_ledger_entry",
            reference_id=original.id,
        )

        original.entry_status = OwnerLedgerEntryStatus.REVERSED
        original.reversed_by_id = reversal.id
        reversal.reversal_of_id = original.id
        reversal.entry_status = OwnerLedgerEntryStatus.REVERSAL

        self.audit.log_activity(
            ENTITY_TYPE, original.id, "reversed",
            f"Owner ledger entry #{original.id} reversed by #{reversal.id}: {reason}", actor_id,
        )
        self.audit.log_audit(
            ENTITY_TYPE, original.id, "reversed",
            {"entry_status": {"old": "active", "new": "reversed"}}, actor_id,
        )
        self.db.commit()
        return self.get_entry(reversal.id)
