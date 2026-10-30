# Business Workflow Layer

## What this is

`app/business_workflows/` is a new orchestration layer that sits **above**
the existing service layer (`app/services/*`). It does not replace or
modify any existing service, repository, model, or API route. Every
existing endpoint continues to behave exactly as before.

A "workflow" here means a complete real-world business process — e.g.
*"activate this lease and set up its payment schedule"*, *"run this
month's rent cycle"*, *"pay this owner what's owed"* — that in practice
already required a staff member (or an API caller) to sequence several
existing endpoints by hand, in the right order, remembering to also
trigger notifications and check dashboards afterwards. This layer
encodes that sequencing once, in code, instead of leaving it as
tribal knowledge.

## Design rules

These are enforced by convention (see each module's docstring) and were
followed throughout:

1. **No database models are declared here.** Nothing in
   `app/business_workflows/` subclasses `BaseModel`/`Base`, defines a
   table, or owns a repository. Workflows read and write data
   exclusively by calling existing services, which already own their
   models and repositories. Status/type constants such as
   `LeaseStatus`, `InstallmentStatus`, and `TransactionType` are
   imported for comparisons only — they are plain string namespaces
   that already live alongside the models, not the models themselves,
   and every existing service in this codebase already imports them
   the same way.
2. **No existing service logic is duplicated or modified.** Every
   business rule (lease status machine, invoice numbering, journal
   posting rules, maintenance status transitions, etc.) still lives in
   exactly one place — its original service. Workflows call those
   services; they never reimplement what a service already does.
3. **Every public workflow method returns a `WorkflowResult`**
   (`app/business_workflows/common.py`) — one predictable response
   shape (`success`, `workflow`, `message`, `data`, `metrics`,
   `notifications_sent`, `accounting_events`, `warnings`), regardless
   of how many subsystems a given workflow touched underneath.
4. **Validation errors still raise `HTTPException`**, exactly like
   every service in `app/services/*`. This layer does not introduce a
   second error-handling convention — a router that calls into it
   needs no new exception handling.
5. **No existing database schema changes.** This phase adds no
   migrations. Every workflow operates on data through the existing
   services/repositories/tables.

## Module map

| Module | Service | Orchestrates |
|---|---|---|
| `lease_workflow_service.py` | `LeaseWorkflowService` | `LeaseService` |
| `rent_cycle/` (sub-package) | `RentCycleService` | `FinancialService`, `RentalService` (own `RentCycle`/`RentCycleRecord` models — see `docs/rent-cycle-engine.md`) |
| `payment/` (sub-package) | `PaymentWorkflowService` | `FinancialService`, `JournalEntryService` (own `Payment`/`PaymentAllocation` models — see `docs/payment-collection-engine.md`) |
| `maintenance_workflow_service.py` | `MaintenanceWorkflowService` | `MaintenanceService`, `FinancialService` |
| `owner_settlement_workflow_service.py` | `OwnerSettlementWorkflowService` | `LeaseService`, `FinancialService` |
| `notification_workflow_service.py` | `NotificationWorkflowService` | `NotificationService`, `LeaseService`, `RentalService`, `FinancialService` |

Every workflow service is constructed the same way as an existing
service — `SomeWorkflowService(db)` — and can be used directly from
Python (as the unit tests do) or wired into a thin API router later
without any change to the workflow layer itself. No routers were added
in this phase, to keep the change strictly additive; see
"Not done in this phase" below.

---

## 1. LeaseWorkflowService

Orchestrates the Owner ↔ Company lease lifecycle
(`app/services/lease_service.py`).

### `activate_lease_with_schedule(lease_id, actor_id, generate_schedule=True)`
Activates a draft lease and, in the same call, generates its
installment schedule — two `LeaseService` calls
(`activate_lease` + `generate_schedule`) that in practice always happen
back-to-back. Notifies admins. Returns the lease dashboard in `metrics`.
If a schedule already exists (e.g. installments were added manually
while still draft), the 409 from `generate_schedule` is caught and
surfaced as a `warnings` entry rather than failing the whole workflow —
the lease itself still activated successfully.

### `renew_lease_and_reschedule(lease_id, new_end_date, actor_id, new_start_date=None, rent_amount=None, notes_summary=None)`
Renews an active lease (via `LeaseService.renew_lease`, which — per its
existing implementation — creates a **new** lease row so the old
contract's history stays intact) and generates the new lease's schedule
in the same call. Notifies admins.

### `terminate_lease_with_notice(lease_id, terminated_date, reason, actor_id)`
Terminates a lease and notifies admins. Adds one workflow-level business
rule beyond what `LeaseService.terminate_lease` itself enforces: a
non-empty termination `reason` is required (the underlying service
accepts an empty string; a workflow-initiated termination should always
be explainable). If the lease's security deposit is still marked
`held`, a warning is added prompting a follow-up settlement — this
workflow does not itself move the deposit, since that's a distinct
decision (return vs. forfeit vs. partial) that shouldn't be inferred.

---

## 2. Rent Cycle Engine

The tenant rent-billing cycle previously had a thin
`RentCycleWorkflowService` here that just sequenced
`FinancialService.generate_bulk_invoices()` +
`RentalService.run_maintenance_sweep()`, with no state of its own.
Phase 14 replaced it with a full **Rent Cycle Engine**
(`app/business_workflows/rent_cycle/`) that gives the monthly cycle a
first-class lifecycle (Draft → Generated → ... → Closed) instead of
being a stateless one-shot call. See **`docs/rent-cycle-engine.md`**
for the complete write-up — this is the one deliberate exception to
design rule #1 above: that sub-package's models
(`app/models/rent_cycle.py`: `RentCycle`, `RentCycleRecord`) are real
new tables, because a rent cycle is a first-class business object with
its own lifecycle, not just an orchestration of others. It still
reuses the existing invoicing/receipt engines underneath rather than
reimplementing them.

---

## 3. Payment & Collection Engine

The tenant-payment-collection side previously had a thin
`PaymentWorkflowService` here — a single call to
`FinancialService.record_invoice_payment()` plus a notification, with
no capture/verify lifecycle of its own. Phase 16 replaced it with a
full **Payment & Collection Engine**
(`app/business_workflows/payment/`) that adds a real two-phase
Pending → Verified lifecycle, multi-invoice allocation ("one payment
covering multiple receipts"), and genuine Refund/Reversal support — see
**`docs/payment-collection-engine.md`** for the complete write-up (the
other deliberate exception to design rule #1 above: that sub-package
owns two new tables, `payments` and `payment_allocations`, for the same
reason `rent_cycle/` owns its own). It still calls
`FinancialService.record_invoice_payment()` for the actual ledger
posting — unchanged, reused, not reimplemented.

---

## 4. MaintenanceWorkflowService

Orchestrates the maintenance request lifecycle together with the
financial ledger.

### `report_and_triage(data, actor_id)`
Creates a request (`MaintenanceService.create_request`) and notifies
admins immediately, escalating to a `warning`-level notification for
`high`/`urgent` priority requests instead of treating every report the
same.

### `complete_and_settle(request_id, completed_date, actor_id, account_id=None)`
Completes a request (`MaintenanceService.complete_request`) and, if it
accrued any material/labor cost (`request.total_actual_cost`, an
existing computed property) **and** an `account_id` was supplied,
books that cost as an `EXPENSE` transaction against the request's
property via `FinancialService.create_transaction()` — which
auto-posts to the general ledger exactly like every other transaction
in this system. `account_id` is optional: a caller that only wants to
mark work done (without settling the expense yet) can omit it, and a
`warnings` entry says so explicitly rather than silently skipping the
posting.

---

## 5. OwnerSettlementWorkflowService

Orchestrates paying an Owner what the company owes them under a Lease
Agreement — the owner-side counterpart to `PaymentWorkflowService`.
No new payment mechanism is introduced: this reuses
`FinancialService.create_transaction()` with
`transaction_type=OWNER_PAYMENT` and `lease_installment_id` set, which
(unchanged, existing behavior) already marks the linked
`LeasePaymentInstallment` paid and auto-posts the journal entry.

### `settle_owner_installment(lease_id, installment_id, account_id, transaction_date, actor_id, payment_method=None, reference_number=None)`
Looks up the installment on the lease, validates it's actually
`pending`/`overdue` (409 otherwise — cannot double-pay), then posts the
`OWNER_PAYMENT` transaction and notifies admins.

### `run_bulk_owner_settlement(account_id, transaction_date, actor_id, owner_id=None, payment_method=None)`
Settles every pending/overdue installment across an owner's active
leases (or, if `owner_id` is omitted, across **all** owners' active
leases). As with `bulk_process_payments`, one failure doesn't abort the
run — results are collected per installment.

---

## 6. NotificationWorkflowService

Cross-cutting notification orchestration, used both directly and
internally by every other workflow service above (so the "notify every
active superuser" fan-out — previously duplicated between
`LeaseService._send_renewal_reminders` and
`RentalService._send_renewal_reminders` — now lives in exactly one
place: `notify_admins()`).

### `notify_admins(title, message, notification_type="info", entity_type=None, entity_id=None)`
The shared fan-out helper: notifies every active superuser, returns how
many were notified. This is what every other workflow service in this
package calls internally.

### `run_daily_notification_sweep(actor_id=None)`
Runs the existing per-module housekeeping sweeps back-to-back —
`LeaseService.run_maintenance_sweep()`,
`RentalService.run_maintenance_sweep()`,
`FinancialService.maintenance_sweep()` — and posts **one** rollup
notification summarizing all three, in addition to whichever targeted
notifications those sweeps already send on their own (e.g. individual
renewal reminders).

### `notify_outstanding_balances(actor_id=None)`
Read-only: summarizes `FinancialService.outstanding_balances()` and
pushes one notification to admins. Triggers no accounting events, since
it doesn't move any money itself.

---

## Standardized response — `WorkflowResult`

```python
class WorkflowResult(BaseModel):
    success: bool = True
    workflow: str                    # e.g. "lease.activate_with_schedule"
    message: str
    data: Optional[Any] = None       # ORM object, dict, or list — see below
    metrics: dict = {}
    notifications_sent: int = 0
    accounting_events: list[str] = []
    warnings: list[str] = []
```

`data` is intentionally left untyped: this layer does not define its
own response schemas beyond the envelope itself. A router that exposes
a given workflow can map `result.data` onto the existing Pydantic
schemas in `app/schemas/*` for its `response_model`, exactly as every
existing router already does for its underlying service's return value.

## Testing

Unit tests live in `backend/tests/test_business_workflows_*.py`, one
file per workflow service, following this repo's existing test
conventions (the `client`/`db_session` fixtures from `tests/conftest.py`
— prerequisite data such as owners/tenants/properties/leases is created
through the real public API, then the workflow itself is exercised
directly against the service layer, since this phase intentionally adds
no new routes). Coverage includes: happy paths, validation failures
(4xx), warning paths that don't hard-fail, and bulk/partial-failure
behavior.

## Not done in this phase (by design)

These notes describe the remaining Phase 12 flat-file modules
(`lease_workflow_service.py`, `maintenance_workflow_service.py`,
`owner_settlement_workflow_service.py`, `notification_workflow_service.py`).
Phase 14 (`rent_cycle/`) and Phase 16 (`payment/`) are both API-facing
and DO add routes and a migration each — see `docs/rent-cycle-engine.md`
and `docs/payment-collection-engine.md`.

- **No new API routes (remaining Phase 12 modules only).** Those four
  services are fully usable from Python today
  (`SomeWorkflowService(db).some_method(...)`). Adding thin routers
  that call into them and map `WorkflowResult.data` onto existing
  response schemas is a natural next step, left out to keep that phase
  strictly additive.
- **No scheduler wiring.** Neither Phase 12's
  `run_daily_notification_sweep` nor Phase 14's rent cycle generation
  step runs on a timer — both are on-demand, same as the existing
  `run_maintenance_sweep()` endpoints they build on (see
  `docs/phase3-renewal-reminders.md` for the existing note on wiring
  those to a real cron/Azure Function timer trigger — the same applies
  here).
- **No schema/migration changes (Phase 12 modules only).** Those five
  services required no new column or table.
