"""
rent_cycle_service.py

The Rent Cycle Engine's public facade — this is what the API router
(app/api/v1/routers/rent_cycles.py) calls, mirroring exactly how every
other router in this codebase calls a single Service class
(LeaseService, MaintenanceService, ...). Internally it just sequences
the other modules in this package:

    RentCycleValidator  -> is this transition/action allowed?
    RentCycleScheduler  -> what are this cycle's dates/number?
    RentCycleGenerator  -> actually run the two existing engines
    RentCycleCloser     -> collection-progress + close/reopen/cancel

Workflow (as specified): Create -> Validate active leases -> Generate
monthly rent records -> Generate receipts -> Update dashboard metrics
-> Notify accounting -> Notify collection team. The "validate active
leases" step is not a separate call here because it isn't separable
from generation without duplicating logic: eligibility is evaluated
lease-by-lease, live, inside FinancialService.generate_bulk_invoices /
RentalService.generate_monthly_receipts (see RentCycleGenerator's
docstring) — re-checking it beforehand with a second query would either
drift from those engines' own rules or just duplicate them.
"""
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.rent_cycle import RentCycle, RentCycleStatus
from app.repositories.rent_cycle_repository import RentCycleRepository, RentCycleRecordRepository
from app.services.audit_service import AuditService
from app.schemas.common import PaginationParams
from app.business_workflows.notification_workflow_service import NotificationWorkflowService
from app.business_workflows.rent_cycle.rent_cycle_validator import RentCycleValidator
from app.business_workflows.rent_cycle.rent_cycle_scheduler import RentCycleScheduler
from app.business_workflows.rent_cycle.rent_cycle_generator import RentCycleGenerator, RentCycleGenerationResult
from app.business_workflows.rent_cycle.rent_cycle_closer import RentCycleCloser
from app.business_workflows.rent_cycle.rent_cycle_exceptions import CycleNotFoundError

ENTITY_TYPE = "rent_cycle"


class RentCycleService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RentCycleRepository(db)
        self.record_repo = RentCycleRecordRepository(db)
        self.validator = RentCycleValidator(db)
        self.scheduler = RentCycleScheduler(db)
        self.generator = RentCycleGenerator(db)
        self.closer = RentCycleCloser(db)
        self.audit = AuditService(db)
        self.notification_workflow = NotificationWorkflowService(db)

    # ---------------- Lookups ----------------
    def get_cycle(self, cycle_id: int) -> RentCycle:
        cycle = self.repo.get_detail(cycle_id)
        if not cycle:
            raise CycleNotFoundError(cycle_id)
        return cycle

    def list_cycles(self, params: PaginationParams, year: Optional[int], cycle_status: Optional[str]):
        return self.repo.list_cycles(
            page=params.page, page_size=params.page_size, year=year, cycle_status=cycle_status,
            sort_by=params.sort_by, sort_dir=params.sort_dir or "desc",
        )

    # ---------------- Create ----------------
    def create_cycle(self, data: dict, actor_id: Optional[int]) -> RentCycle:
        year, month = data["year"], data["month"]
        self.validator.validate_no_duplicate_cycle(year, month)

        start_date = data.get("start_date") or self.scheduler.default_start_date(year, month)
        due_date = data.get("due_date") or self.scheduler.default_due_date(start_date)
        self.validator.validate_dates(start_date, due_date)

        payload = {
            "cycle_number": self.scheduler.next_cycle_number(),
            "month": month,
            "year": year,
            "start_date": start_date,
            "due_date": due_date,
            "cycle_status": RentCycleStatus.DRAFT,
            "property_ids": data.get("property_ids"),
            "notes": data.get("notes"),
        }
        cycle = self.repo.create(payload, actor_id=actor_id)
        self.audit.log_activity(ENTITY_TYPE, cycle.id, "created", f"Rent cycle {cycle.cycle_number} created for {year}-{month:02d}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, cycle.id, "created", None, actor_id)
        self.db.commit()
        return self.get_cycle(cycle.id)

    # ---------------- Generate ----------------
    def generate(self, cycle_id: int, actor_id: Optional[int], is_admin: bool, force: bool = False) -> tuple[RentCycle, RentCycleGenerationResult]:
        """Runs the generation workflow: validate -> generate records ->
        update status -> notify accounting -> notify collection team.

        If the cycle was already generated and `force` isn't set, this
        is a safe no-op (returns the cycle as-is, with a zero-count
        result) rather than an error — matches how, e.g.,
        FinancialService.generate_bulk_invoices is itself idempotent per
        period rather than erroring on a second call. Regenerating an
        already-generated cycle at all requires `force=True`, which in
        turn requires the caller to be an administrator (see
        RentCycleValidator.validate_can_generate).
        """
        cycle = self.get_cycle(cycle_id)
        self.validator.validate_can_generate(cycle, force=force, is_admin=is_admin)

        already_generated = cycle.cycle_status != RentCycleStatus.DRAFT
        if already_generated and not force:
            return cycle, RentCycleGenerationResult(invoices_generated=0, receipts_generated=0, leases_skipped=0)

        result = self.generator.generate(cycle, actor_id=actor_id)

        cycle.cycle_status = RentCycleStatus.GENERATED
        cycle.generated_at = datetime.now(timezone.utc)
        self.db.commit()

        action = "regenerated" if already_generated else "generated"
        self.audit.log_activity(
            ENTITY_TYPE, cycle.id, action,
            f"Rent cycle {cycle.cycle_number} {action}: {result.invoices_generated} invoice(s), "
            f"{result.receipts_generated} receipt(s)",
            actor_id,
        )
        self.audit.log_audit(ENTITY_TYPE, cycle.id, action, {"cycle_status": {"old": "draft", "new": "generated"}}, actor_id)

        self.notification_workflow.notify_admins(
            title="Rent cycle generated — accounting",
            message=f"Rent cycle {cycle.cycle_number} ({cycle.year}-{cycle.month:02d}) generated: "
                    f"{result.invoices_generated} invoice(s) posted for collection.",
            notification_type="info",
            entity_type=ENTITY_TYPE,
            entity_id=cycle.id,
        )
        self.notification_workflow.notify_admins(
            title="Rent cycle ready for collection",
            message=f"Rent cycle {cycle.cycle_number} ({cycle.year}-{cycle.month:02d}) is ready: "
                    f"{result.receipts_generated} receipt(s) generated for the collection team.",
            notification_type="info",
            entity_type=ENTITY_TYPE,
            entity_id=cycle.id,
        )

        return self.get_cycle(cycle.id), result

    # ---------------- Close / Reopen / Cancel ----------------
    def close_cycle(self, cycle_id: int, notes: Optional[str], actor_id: Optional[int]) -> RentCycle:
        cycle = self.get_cycle(cycle_id)
        self.closer.refresh_status(cycle)
        self.validator.validate_can_close(cycle)
        old_status = cycle.cycle_status
        self.closer.close(cycle, notes)
        self.db.commit()
        self.audit.log_activity(ENTITY_TYPE, cycle.id, "closed", f"Rent cycle {cycle.cycle_number} closed", actor_id)
        self.audit.log_audit(ENTITY_TYPE, cycle.id, "closed", {"cycle_status": {"old": old_status, "new": "closed"}}, actor_id)
        return self.get_cycle(cycle.id)

    def reopen_cycle(self, cycle_id: int, actor_id: Optional[int]) -> RentCycle:
        cycle = self.get_cycle(cycle_id)
        self.validator.validate_can_reopen(cycle)
        self.closer.reopen(cycle)
        self.db.commit()
        self.audit.log_activity(ENTITY_TYPE, cycle.id, "reopened", f"Rent cycle {cycle.cycle_number} reopened", actor_id)
        self.audit.log_audit(ENTITY_TYPE, cycle.id, "reopened", {"cycle_status": {"old": "closed", "new": cycle.cycle_status}}, actor_id)
        return self.get_cycle(cycle.id)

    def cancel_cycle(self, cycle_id: int, reason: str, actor_id: Optional[int]) -> RentCycle:
        cycle = self.get_cycle(cycle_id)
        self.validator.validate_can_cancel(cycle, reason)
        old_status = cycle.cycle_status
        self.closer.cancel(cycle, reason)
        self.db.commit()
        self.audit.log_activity(ENTITY_TYPE, cycle.id, "cancelled", f"Rent cycle {cycle.cycle_number} cancelled: {reason}", actor_id)
        self.audit.log_audit(ENTITY_TYPE, cycle.id, "cancelled", {"cycle_status": {"old": old_status, "new": "cancelled"}}, actor_id)
        self.notification_workflow.notify_admins(
            title="Rent cycle cancelled",
            message=f"Rent cycle {cycle.cycle_number} was cancelled: {reason}",
            notification_type="warning",
            entity_type=ENTITY_TYPE,
            entity_id=cycle.id,
        )
        return self.get_cycle(cycle.id)

    # ---------------- Dashboard ----------------
    def dashboard(self) -> dict:
        counts = self.repo.dashboard_counts()
        today = date.today()
        current = self.repo.get_by_period(today.year, today.month)

        metrics = {
            **counts,
            "current_cycle_number": None,
            "total_receipts": 0,
            "total_expected_income": 0,
            "total_collected_income": 0,
            "active_lease_count": 0,
            "generated_receipt_count": 0,
            "collection_progress_percent": 0,
        }
        if current:
            current = self.get_cycle(current.id)
            progress = self.closer.compute_progress(current)
            metrics.update({
                "current_cycle_number": current.cycle_number,
                "total_receipts": len([r for r in current.records if r.invoice_id]),
                "total_expected_income": progress.total_expected,
                "total_collected_income": progress.total_collected,
                "active_lease_count": len(current.records),
                "generated_receipt_count": len([r for r in current.records if r.installment_id]),
                "collection_progress_percent": progress.percent,
            })
        return metrics
