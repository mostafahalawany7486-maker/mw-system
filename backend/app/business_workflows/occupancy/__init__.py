"""
Occupancy & Unit Lifecycle Engine (Phase 18).

Replaces dependence on `Property.availability_status` (a plain stored
column, manually set in exactly two places — see
docs/occupancy-engine.md's "Conflicts found" section) with a fully
computed, live occupancy status for every unit: never stored, always
derived from the actual source-of-truth tables (RentalContract,
MaintenanceRequest), plus two new small supporting tables for the
handful of statuses that had no other event source anywhere in this
codebase (UnitOccupancyOverride) and the audit trail
(OccupancyStatusHistory).

Like rent_cycle/, payment/, and owner_ledger/, this is a sub-package
that owns its own SQLAlchemy models (app/models/occupancy.py) rather
than being pure orchestration — see
app/business_workflows/__init__.py's docstring for why that's a
deliberate, narrow exception, now extended a fourth time.

Module map:
  occupancy_engine.py       Pure status computation (the core) + the audit-log write path
  occupancy_statistics.py   Dashboard / building-summary aggregation on top of the engine
  occupancy_events.py       Set/clear override, record move-out notice
  occupancy_scheduler.py    The on-demand recalculate-and-log sweep (POST /occupancy/recalculate)
  occupancy_service.py      Facade — the one thing the API router calls
  occupancy_validator.py    Every business rule + this package's exceptions
"""
from app.business_workflows.occupancy.occupancy_service import OccupancyService
from app.business_workflows.occupancy.occupancy_engine import OccupancyEngine
from app.business_workflows.occupancy.occupancy_statistics import OccupancyStatisticsService
from app.business_workflows.occupancy.occupancy_events import OccupancyEventsService
from app.business_workflows.occupancy.occupancy_scheduler import OccupancyScheduler
from app.business_workflows.occupancy.occupancy_validator import (
    OccupancyValidator, OccupancyError, UnitNotFoundError, BuildingNotFoundError,
    ReservationConflictError, MaintenanceConflictError, DuplicateOccupancyStateError,
    OverrideNotFoundError, OverrideAlreadyClearedError, MultipleActiveLeasesError,
)

__all__ = [
    "OccupancyService", "OccupancyEngine", "OccupancyStatisticsService", "OccupancyEventsService", "OccupancyScheduler",
    "OccupancyValidator", "OccupancyError", "UnitNotFoundError", "BuildingNotFoundError",
    "ReservationConflictError", "MaintenanceConflictError", "DuplicateOccupancyStateError",
    "OverrideNotFoundError", "OverrideAlreadyClearedError", "MultipleActiveLeasesError",
]
