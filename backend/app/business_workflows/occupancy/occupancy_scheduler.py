"""
occupancy_scheduler.py

"Automatic" here means the same thing it already means everywhere else
in this codebase: there is no real background job runner (see
LeaseWorkflowService's renewal sweep and NotificationWorkflowService's
daily sweep — both documented as "no scheduler exists in this stack,
wire this to a real cron in production"). This sweep is the occupancy
equivalent: POST /occupancy/recalculate runs it on demand, and a real
deployment should point an external cron (or Azure/Render's own
scheduled-job feature) at that endpoint on a regular interval (every
few minutes is reasonable — this is push-button diagnostics/audit
maintenance, not the source of truth for what a unit's status is right
now; every GET endpoint already computes that live, unaffected by
whether or when this has last run).

What running the sweep actually does: walk every unit (or every unit in
one building, if scoped), call OccupancyEngine.recalculate_and_log()
for each, and collect whichever ones produced a logged change. This is
the mechanism that satisfies "every status change must be recorded"
without requiring hooks into RentalService/MaintenanceService (which
would invert this codebase's layering — services must never depend on
business_workflows, only the reverse — see
app/business_workflows/__init__.py's docstring).
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.business_workflows.occupancy.occupancy_engine import OccupancyEngine
from app.business_workflows.occupancy.occupancy_statistics import OccupancyStatisticsService
from app.repositories.property_repository import PropertyRepository


class OccupancyScheduler:
    def __init__(self, db: Session):
        self.db = db
        self.engine = OccupancyEngine(db)
        self.stats = OccupancyStatisticsService(db)
        self.property_repo = PropertyRepository(db)

    def run_sweep(self, building_id: Optional[int], actor_id: Optional[int]) -> dict:
        unit_ids = self.property_repo.get_unit_ids(building_id) if building_id is not None else self.stats._all_unit_ids()

        changes = []
        for unit_id in unit_ids:
            change = self.engine.recalculate_and_log(unit_id, actor_id, triggered_by="recalculate")
            if change:
                changes.append(change)

        return {
            "units_checked": len(unit_ids),
            "units_changed": len(changes),
            "changes": changes,
        }
