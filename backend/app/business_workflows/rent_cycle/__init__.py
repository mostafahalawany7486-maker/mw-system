"""
Rent Cycle Engine (Phase 14).

The central component responsible for the monthly rent collection
process. Replaces "generate invoices one billing period at a time via a
direct FinancialService call" with a first-class RentCycle entity that
has its own lifecycle (Draft -> Generated -> Printed -> Distributed ->
Collecting -> Partially Collected -> Completed -> Closed, or Cancelled
from most non-terminal states) — see docs/rent-cycle-engine.md for the
full design write-up.

This is the one sub-package under app/business_workflows/ that owns its
own SQLAlchemy models (app/models/rent_cycle.py) rather than being pure
orchestration — see the package-level docstring in
app/business_workflows/__init__.py for why.

Public entry point: RentCycleService (rent_cycle_service.py), used
directly by app/api/v1/routers/rent_cycles.py, exactly like every other
router in this codebase calls its module's Service class.
"""
from app.business_workflows.rent_cycle.rent_cycle_service import RentCycleService
from app.business_workflows.rent_cycle.rent_cycle_validator import RentCycleValidator
from app.business_workflows.rent_cycle.rent_cycle_scheduler import RentCycleScheduler
from app.business_workflows.rent_cycle.rent_cycle_generator import RentCycleGenerator, RentCycleGenerationResult
from app.business_workflows.rent_cycle.rent_cycle_closer import RentCycleCloser, CollectionProgress
from app.business_workflows.rent_cycle.rent_cycle_exceptions import (
    RentCycleError, CycleNotFoundError, DuplicateCycleError, InvalidCycleStatusTransitionError,
    RegenerationNotAuthorizedError, CycleValidationError,
)

__all__ = [
    "RentCycleService",
    "RentCycleValidator",
    "RentCycleScheduler",
    "RentCycleGenerator", "RentCycleGenerationResult",
    "RentCycleCloser", "CollectionProgress",
    "RentCycleError", "CycleNotFoundError", "DuplicateCycleError",
    "InvalidCycleStatusTransitionError", "RegenerationNotAuthorizedError", "CycleValidationError",
]
