"""
occupancy_engine.py

The heart of this module: computing a unit's TRUE current operational
status live, every time, from the actual source-of-truth tables — never
from a stored status column. This is what "Never depend on manual
status updates" and "Occupancy calculated automatically" mean in
practice: there is no `Property.occupancy_status` column to forget to
update. Call compute_unit_status() and the answer is always correct as
of right now.

Priority order (highest wins — a unit has exactly one status):
  1. Administrative override, if active (Inactive > Blocked > Renovation
     > Cleaning > Inspection > Reserved) — an explicit staff decision
     always outranks what the data would otherwise suggest. See
     UnitOccupancyOverride / OccupancyStatus.OVERRIDABLE.
  2. Open MaintenanceRequest → Under Maintenance. Matches the spec's own
     example ("Maintenance Request Open → Under Maintenance")
     literally and unconditionally — including outranking an active
     lease. Documented trade-off: a tenant can, in reality, still be
     living in a unit that also has an open maintenance ticket; this
     engine reports one status per unit, not a compound state, and the
     spec's example is explicit about which one wins. The maintenance
     request and the lease are both still independently visible via
     their own modules either way — nothing about the underlying data
     is hidden, only which single label the dashboard shows.
  3. Active lease with move_out_notice_date set → Notice Period.
  4. Active lease approaching its own end_date (is_expiring_soon, no
     notice given) → Vacating Soon.
  5. Active lease, nothing else → Occupied.
  6. Nothing else applies → Available (the true default/fallback —
     never stored, never set directly, just what's left over).

Audit trail: see recalculate_and_log() at the bottom. The engine itself
never writes anything when just answering "what's the status right
now" — recalculate_and_log() is the one place a computed answer gets
turned into a logged, auditable event, by diffing against the last
logged value for that unit.
"""
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session

from app.models.occupancy import OccupancyStatus
from app.repositories.occupancy_repository import OccupancyOverrideRepository, OccupancyHistoryRepository, OccupancyDataRepository
from app.services.audit_service import AuditService

ENTITY_TYPE = "occupancy_status"

# Override statuses in priority order, highest first — see module docstring.
_OVERRIDE_PRIORITY = [
    OccupancyStatus.INACTIVE, OccupancyStatus.BLOCKED, OccupancyStatus.RENOVATION,
    OccupancyStatus.CLEANING, OccupancyStatus.INSPECTION, OccupancyStatus.RESERVED,
]


class OccupancyEngine:
    def __init__(self, db: Session):
        self.db = db
        self.override_repo = OccupancyOverrideRepository(db)
        self.history_repo = OccupancyHistoryRepository(db)
        self.data_repo = OccupancyDataRepository(db)
        self.audit = AuditService(db)

    def compute_unit_status(self, property_id: int) -> tuple[str, str]:
        """Returns (status, reason) for a single unit. One query round
        trip per source (override lookup, active-contract lookup,
        open-maintenance check) — see compute_bulk() for the
        building/dashboard-scale version that batches all three."""
        override = self.override_repo.get_active_for_unit(property_id)
        if override:
            return override.override_status, f"Administrative override: {override.reason or override.override_status}"

        if self.data_repo.has_open_maintenance(property_id):
            return OccupancyStatus.UNDER_MAINTENANCE, "Open maintenance request"

        contract = self.data_repo.get_active_contract(property_id)
        if contract:
            return self._status_from_contract(contract)

        return OccupancyStatus.AVAILABLE, "No active lease, override, or open maintenance request"

    def compute_bulk(self, property_ids: list[int]) -> dict[int, tuple[str, str]]:
        """Same computation as compute_unit_status, batched — 3 queries
        total regardless of how many units, instead of 3*N. This is
        what every dashboard/building-summary/units-list endpoint
        actually calls; compute_unit_status() exists for the single-
        unit case (e.g. a unit's own detail page) where the simpler
        per-call version reads more clearly and the cost difference is
        irrelevant."""
        if not property_ids:
            return {}
        overrides = self.override_repo.get_active_for_units(property_ids)
        maintenance_ids = self.data_repo.open_maintenance_unit_ids(property_ids)
        contracts = self.data_repo.get_active_contracts_for_units(property_ids)

        result: dict[int, tuple[str, str]] = {}
        for pid in property_ids:
            if pid in overrides:
                o = overrides[pid]
                result[pid] = (o.override_status, f"Administrative override: {o.reason or o.override_status}")
            elif pid in maintenance_ids:
                result[pid] = (OccupancyStatus.UNDER_MAINTENANCE, "Open maintenance request")
            elif pid in contracts:
                result[pid] = self._status_from_contract(contracts[pid])
            else:
                result[pid] = (OccupancyStatus.AVAILABLE, "No active lease, override, or open maintenance request")
        return result

    def _status_from_contract(self, contract) -> tuple[str, str]:
        if contract.move_out_notice_date is not None:
            return OccupancyStatus.NOTICE_PERIOD, f"Tenant gave move-out notice, effective {contract.move_out_notice_date}"
        if contract.is_expiring_soon:
            return OccupancyStatus.VACATING_SOON, f"Contract {contract.contract_number} ends {contract.end_date} (within its renewal notice window)"
        return OccupancyStatus.OCCUPIED, f"Active contract {contract.contract_number} through {contract.end_date}"

    # ---------------- Audit trail ----------------
    def recalculate_and_log(self, property_id: int, actor_id: Optional[int], triggered_by: str = "recalculate") -> Optional[dict]:
        """Computes the current status and, if it differs from the last
        LOGGED status for this unit, writes one OccupancyStatusHistory
        row and returns it as a dict. Returns None if nothing changed
        (the common case — most recalculations find no change, and
        logging a row every time would make the "audit trail" useless
        noise instead of a real record of *changes*)."""
        new_status, reason = self.compute_unit_status(property_id)
        previous_status = self.history_repo.get_last_status(property_id)

        if previous_status == new_status:
            return None

        entry = self.history_repo.create({
            "property_id": property_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "reason": reason,
            "triggered_by": triggered_by,
        }, actor_id=actor_id)
        self.db.commit()

        self.audit.log_activity(
            ENTITY_TYPE, property_id, "status_changed",
            f"Unit {property_id} occupancy status changed: {previous_status or '(none yet)'} → {new_status} ({reason})",
            actor_id,
        )
        return {
            "id": entry.id, "property_id": property_id, "previous_status": previous_status,
            "new_status": new_status, "reason": reason, "triggered_by": triggered_by, "changed_at": entry.changed_at,
        }
