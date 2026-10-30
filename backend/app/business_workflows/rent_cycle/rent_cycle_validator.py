"""
rent_cycle_validator.py

Every business rule for what state transitions a RentCycle may legally
make. Kept separate from rent_cycle_service.py so the rules (what's
allowed) are easy to read/audit independently of the orchestration
(what happens when they pass) — mirrors how, e.g., MaintenanceService
keeps its own ALLOWED_TRANSITIONS table separate from the methods that
use it.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.rent_cycle import RentCycle, RentCycleStatus
from app.repositories.rent_cycle_repository import RentCycleRepository
from app.business_workflows.rent_cycle.rent_cycle_exceptions import (
    DuplicateCycleError, InvalidCycleStatusTransitionError, RegenerationNotAuthorizedError,
    CycleValidationError,
)

# What "generate" is allowed to move a cycle *from*. A cycle that's
# already CLOSED or CANCELLED can never be generated into again — full
# stop, no admin override, since those are terminal states.
GENERATABLE_FROM = {
    RentCycleStatus.DRAFT, RentCycleStatus.GENERATED, RentCycleStatus.PRINTED,
    RentCycleStatus.DISTRIBUTED, RentCycleStatus.COLLECTING, RentCycleStatus.PARTIALLY_COLLECTED,
}
CLOSABLE_FROM = {
    RentCycleStatus.COLLECTING, RentCycleStatus.PARTIALLY_COLLECTED, RentCycleStatus.COMPLETED,
}
REOPENABLE_FROM = {RentCycleStatus.CLOSED}
ALL_STATUSES = {
    RentCycleStatus.DRAFT, RentCycleStatus.GENERATED, RentCycleStatus.PRINTED,
    RentCycleStatus.DISTRIBUTED, RentCycleStatus.COLLECTING, RentCycleStatus.PARTIALLY_COLLECTED,
    RentCycleStatus.COMPLETED, RentCycleStatus.CLOSED, RentCycleStatus.CANCELLED,
}
# Anything not already terminal (CLOSED/CANCELLED) can be cancelled.
CANCELLABLE_FROM = ALL_STATUSES - RentCycleStatus.TERMINAL


class RentCycleValidator:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RentCycleRepository(db)

    def validate_no_duplicate_cycle(self, year: int, month: int) -> None:
        existing = self.repo.get_by_period(year, month)
        if existing:
            raise DuplicateCycleError(year, month, existing.cycle_number)

    def validate_dates(self, start_date, due_date) -> None:
        if due_date <= start_date:
            raise CycleValidationError("due_date must be after start_date")

    def validate_can_generate(self, cycle: RentCycle, force: bool, is_admin: bool) -> None:
        if cycle.cycle_status not in GENERATABLE_FROM:
            raise InvalidCycleStatusTransitionError(cycle.cycle_status, "generate")
        already_generated = cycle.cycle_status != RentCycleStatus.DRAFT
        if already_generated and not force:
            # Not itself an error: rent_cycle_service treats "already
            # generated, no force flag" as a no-op regeneration guard,
            # not a hard failure — see its docstring. This validator
            # only enforces the *authorization* rule below.
            return
        if already_generated and force and not is_admin:
            raise RegenerationNotAuthorizedError()

    def validate_can_close(self, cycle: RentCycle) -> None:
        if cycle.cycle_status not in CLOSABLE_FROM:
            raise InvalidCycleStatusTransitionError(cycle.cycle_status, "close")

    def validate_can_reopen(self, cycle: RentCycle) -> None:
        if cycle.cycle_status not in REOPENABLE_FROM:
            raise InvalidCycleStatusTransitionError(cycle.cycle_status, "reopen")

    def validate_can_cancel(self, cycle: RentCycle, reason: Optional[str]) -> None:
        if cycle.cycle_status not in CANCELLABLE_FROM:
            raise InvalidCycleStatusTransitionError(cycle.cycle_status, "cancel")
        if not reason or not reason.strip():
            raise CycleValidationError("A cancellation reason is required")
