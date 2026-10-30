"""
Business Workflow Layer (Phase 12+14+16+17+18+19).

This package sits ABOVE the existing service layer (app/services/*) and
orchestrates it into complete, real-world business processes — e.g.
"settle an owner's rent", "close out a maintenance request", "run the
monthly rent cycle", "capture and verify a tenant payment", "record a
recoverable expense", "compute a unit's real occupancy status", "run
the security deposit lifecycle" — instead of exposing another set of
CRUD operations.

Hard rules for everything in this package (see docs/business-workflows.md,
docs/rent-cycle-engine.md, docs/payment-collection-engine.md,
docs/owner-ledger-engine.md, docs/occupancy-engine.md, and
docs/financial-engine.md for the full write-ups):

  1. No SQLAlchemy models are declared here, with five deliberate,
     narrow exceptions: app/business_workflows/rent_cycle/ (Phase 14),
     app/business_workflows/payment/ (Phase 16),
     app/business_workflows/owner_ledger/ (Phase 17),
     app/business_workflows/occupancy/ (Phase 18), and
     app/business_workflows/financial_engine/ (Phase 19) each own new
     tables (RentCycle/RentCycleRecord; Payment/PaymentAllocation;
     OwnerLedgerEntry; UnitOccupancyOverride/OccupancyStatusHistory;
     DepositLedgerEntry) because each is a first-class business object/
     concern with its own lifecycle or audit trail — not just an
     orchestration of others. Those models live in app/models/ (not
     inside business_workflows/), exactly like every other module's
     models, and are accessed through app/repositories/ — same Clean
     Architecture layering as the rest of the system. Everything else
     in this package remains pure orchestration: it reads/writes data
     exclusively through the existing services in app/services/*, which
     already own their own repositories and models. Status/type
     constants (e.g. LeaseStatus, InstallmentStatus) are imported for
     comparisons only — they are plain string namespaces, not
     declarative models.
  1a. This package may call app/services/*, never the reverse — no
     service under app/services/ imports from business_workflows/. This
     is why occupancy/ computes status by querying RentalContract and
     MaintenanceRequest data directly through their own repositories
     rather than by hooking into RentalService/MaintenanceService's
     mutation methods: a hook would require those services to call back
     into this package, inverting the layering. See
     occupancy_scheduler.py's module docstring for the full reasoning.
  2. No existing service method is modified, removed, or duplicated.
     Workflows call services; they never re-implement what a service
     already does. This also applies WITHIN this package: when a later
     phase's dedicated sub-package covers the same capability as an
     earlier phase's simpler flat-file workflow, the earlier one is
     retired rather than left running alongside a newer, overlapping
     implementation (payment_workflow_service.py and
     rent_cycle_workflow_service.py, both Phase 12, were each retired
     this way). When a later phase's capability instead only
     *overlaps partially* with an earlier one — as Phase 17's
     owner_settlement_service.py does with Phase 12's
     OwnerSettlementWorkflowService, or as Phase 19's financial_engine/
     does with the Payment Engine, Owner Ledger, and
     FinancialService.create_transfer/create_transaction wholesale — the
     earlier one is left untouched and the new one *wraps* it (delegates
     the actual work, adds only the genuinely new behavior) rather than
     either duplicating or retiring it. See docs/owner-ledger-engine.md
     and docs/financial-engine.md.
  3. Every public workflow method returns a `WorkflowResult` (see
     common.py) so callers get one predictable response shape back,
     regardless of how many subsystems a given workflow touches. (The
     rent_cycle/, payment/, owner_ledger/, occupancy/, and
     financial_engine/ sub-packages are API-facing and use their own
     Pydantic response schemas in app/schemas/rent_cycle.py /
     app/schemas/payment.py / app/schemas/owner_ledger.py /
     app/schemas/occupancy.py / app/schemas/financial_engine.py instead,
     matching how every other API-facing module in this codebase —
     leases, rentals, financial, etc. — already returns its own schemas
     rather than a generic envelope.)
  4. Validation errors are raised as `HTTPException`, exactly like the
     rest of the codebase — this package does not introduce a second
     error-handling convention.

Each module below owns one business capability:

  - lease_workflow_service.py             Owner <-> Company lease lifecycle
  - rent_cycle/                           Monthly rent cycle engine (Phase 14)
  - payment/                              Payment & collection engine (Phase 16)
  - owner_ledger/                         Owner ledger & recoverable expenses (Phase 17)
  - occupancy/                            Occupancy & unit lifecycle engine (Phase 18)
  - financial_engine/                     Cross-entity financial ledgers & security deposits (Phase 19)
  - maintenance_workflow_service.py       Maintenance request lifecycle
  - owner_settlement_workflow_service.py  Owner lease payouts
  - notification_workflow_service.py      Cross-cutting notification sweeps
"""
from app.business_workflows.common import WorkflowResult
from app.business_workflows.lease_workflow_service import LeaseWorkflowService
from app.business_workflows.maintenance_workflow_service import MaintenanceWorkflowService
from app.business_workflows.owner_settlement_workflow_service import OwnerSettlementWorkflowService
from app.business_workflows.notification_workflow_service import NotificationWorkflowService
from app.business_workflows.rent_cycle.rent_cycle_service import RentCycleService
from app.business_workflows.payment.payment_workflow_service import PaymentWorkflowService
from app.business_workflows.owner_ledger.owner_ledger_service import OwnerLedgerService
from app.business_workflows.occupancy.occupancy_service import OccupancyService
from app.business_workflows.financial_engine.financial_engine import FinancialEngine

__all__ = [
    "WorkflowResult",
    "LeaseWorkflowService",
    "MaintenanceWorkflowService",
    "OwnerSettlementWorkflowService",
    "NotificationWorkflowService",
    "RentCycleService",
    "PaymentWorkflowService",
    "OwnerLedgerService",
    "OccupancyService",
    "FinancialEngine",
]
