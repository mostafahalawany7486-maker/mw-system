"""
occupancy_events.py

The few genuine "write" actions this module owns: setting/clearing an
administrative override, and recording that a tenant gave move-out
notice. Every write here is followed by
OccupancyEngine.recalculate_and_log() so the change is immediately
reflected in the audit trail — the spec's "Every status change must be
recorded" applies to these explicit actions just as much as it does to
the passive recalculate sweep (occupancy_scheduler.py).
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.repositories.occupancy_repository import OccupancyOverrideRepository
from app.repositories.rental_repository import RentalContractRepository
from app.business_workflows.occupancy.occupancy_engine import OccupancyEngine
from app.business_workflows.occupancy.occupancy_validator import OccupancyValidator, OverrideNotFoundError

ENTITY_TYPE = "unit_occupancy_override"


class OccupancyEventsService:
    def __init__(self, db: Session):
        self.db = db
        self.override_repo = OccupancyOverrideRepository(db)
        self.contract_repo = RentalContractRepository(db)
        self.validator = OccupancyValidator(db)
        self.engine = OccupancyEngine(db)

    def set_override(self, property_id: int, override_status: str, reason: Optional[str], expires_at: Optional[datetime], actor_id: Optional[int]):
        self.validator.validate_unit_exists(property_id)
        computed_status, _ = self.engine.compute_unit_status(property_id)
        self.validator.validate_can_set_override(property_id, override_status, computed_status)

        override = self.override_repo.create({
            "property_id": property_id, "override_status": override_status, "reason": reason,
            "set_by": actor_id, "expires_at": expires_at,
        }, actor_id=actor_id)
        self.db.commit()

        self.engine.recalculate_and_log(property_id, actor_id, triggered_by="override_set")
        self.db.commit()
        return self.override_repo.get_detail(override.id)

    def clear_override(self, override_id: int, reason: Optional[str], actor_id: Optional[int]):
        override = self.override_repo.get_detail(override_id)
        if not override:
            raise OverrideNotFoundError(override_id)
        self.validator.validate_can_clear_override(override)

        override.cleared_at = datetime.utcnow()
        override.cleared_by = actor_id
        override.clear_reason = reason
        self.db.commit()

        self.engine.recalculate_and_log(override.property_id, actor_id, triggered_by="override_cleared")
        self.db.commit()
        return self.override_repo.get_detail(override_id)

    def set_move_out_notice(self, contract_id: int, notice_date, actor_id: Optional[int]):
        """Records that a tenant gave move-out notice — the fact that
        distinguishes Notice Period from Vacating Soon (see
        occupancy_engine.py). Deliberately lives here, not on
        RentalService, since it's an occupancy-lifecycle concept the
        Rentals module itself has no other reason to know about; the
        contract row is simply where the fact is stored (see migration
        0022's docstring)."""
        contract = self.contract_repo.get_detail(contract_id)
        if not contract:
            from app.business_workflows.occupancy.occupancy_validator import OccupancyError
            from fastapi import status
            raise OccupancyError(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rental contract {contract_id} not found")

        contract.move_out_notice_date = notice_date
        self.db.commit()

        self.engine.recalculate_and_log(contract.property_id, actor_id, triggered_by="notice_given")
        self.db.commit()
        return contract
