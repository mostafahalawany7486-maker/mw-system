"""
ledger_sync_service.py

Spec: "Prevent ledger imbalance." Because every ledger view in this
module is computed live from one shared source of truth (Transaction,
plus DepositLedgerEntry for deposits — see balance_service.py's module
docstring), there is no multi-ledger synchronization problem to solve
by construction: nothing here is a separate copy that could drift out
of sync with another copy.

What this file actually does, honestly: a diagnostic/integrity check,
not a sync job. It verifies the one place a running total genuinely IS
stored — DepositLedgerEntry.balance_after — is internally consistent
(each entry's balance_after equals the previous entry's balance_after
plus/minus that entry's own effect), the same verification pattern
already established for OwnerLedgerEntry
(OwnerBalanceService.recompute_and_verify, Phase 17). Exposed for
ops/support use and exercised directly in tests; no write path in this
module depends on it.
"""
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.financial_engine import DepositAction
from app.repositories.deposit_repository import DepositLedgerRepository


class LedgerSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.deposit_repo = DepositLedgerRepository(db)

    def verify_deposit_ledger(self, contract_type: str, contract_id: int) -> dict:
        entries = self.deposit_repo.list_for_contract(contract_type, contract_id)
        running = Decimal("0")
        mismatches = []
        for entry in entries:
            if entry.action == DepositAction.RECEIVED:
                running = entry.amount
            elif entry.action in (DepositAction.PARTIAL_REFUND, DepositAction.FULL_REFUND, DepositAction.DEDUCTION, DepositAction.FORFEIT, DepositAction.TRANSFER_TO_OWNER):
                running -= entry.amount
            if running != entry.balance_after:
                mismatches.append({"entry_id": entry.id, "expected": running, "recorded": entry.balance_after})
                running = entry.balance_after  # keep checking forward from the recorded value, don't cascade one mismatch into every later row

        return {
            "contract_type": contract_type,
            "contract_id": contract_id,
            "entries_checked": len(entries),
            "is_consistent": len(mismatches) == 0,
            "mismatches": mismatches,
        }
