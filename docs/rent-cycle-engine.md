# Rent Cycle Engine (Phase 14)

## Pre-implementation analysis (required before any code was written)

Two existing engines already cover the mechanics of monthly rent
collection, and neither was touched:

1. **Rent Billing Engine** (`FinancialService.generate_bulk_invoices`,
   Phase 8/10) — generates one `Invoice` per active rental contract for
   a billing period, idempotent per `(contract, billing_period_start)`,
   respecting each contract's own billing frequency. This already *is*
   "load active leases, skip expired/cancelled/future leases, generate
   a rent record per eligible lease, never duplicate" — see
   `RentalContractRepository.list_active_for_billing`
   (`start_date <= as_of <= end_date`, `contract_status == active`) and
   `InvoiceRepository.exists_for_period`.
2. **Rental Receipt Module** (`RentalService.generate_monthly_receipts`,
   Phase 7) — assigns a `receipt_number` to every
   `RentalPaymentInstallment` due in a given `(year, month)`, for active
   contracts only, print-before-payment. This is the "automatically
   generate rent receipts for every active lease" requirement, already
   built.

What did **not** exist: a single entity representing the monthly cycle
itself, with a real lifecycle (Draft → ... → Closed) a branch manager
can look at. That's what this phase adds — `RentCycle`, a thin
orchestration/reporting layer **over** the two engines above, not a
replacement for either. Existing invoice numbering, receipt formatting,
and journal posting are completely unchanged.

## Business flow

```
Create Rent Cycle (Draft)
        |
        v
Generate  ──►  FinancialService.generate_bulk_invoices()   (existing, unmodified)
        │            "load active leases, skip expired/cancelled/
        │             future, one Invoice per eligible lease"
        │
        ├──►  RentalService.generate_monthly_receipts()     (existing, unmodified)
        │            "assign a receipt_number to every installment
        │             due this month, active contracts only"
        │
        ├──►  One RentCycleRecord per lease touched by either engine
        │            (cycle_id, rental_contract_id) is UNIQUE — this is
        │            what makes duplicate generation impossible at the
        │             database level, on top of both engines already
        │             being idempotent per period on their own.
        │
        ├──►  Notify Accounting        (in-app notification, all admins)
        └──►  Notify Collection Team   (in-app notification, all admins)
        │
        v
Generated ──► (payments come in via the existing Financial module,
               completely unchanged) ──► Collecting / Partially
               Collected / Completed (auto-computed from live Invoice
               status every time the cycle is read or closed)
        │
        v
     Closed  ◄──────────────► Reopened
        │
        v
    Cancelled (from any non-terminal state, with a mandatory reason)
```

"Validate active leases" is not a separate step with its own endpoint:
eligibility is evaluated lease-by-lease, live, *inside*
`generate_bulk_invoices`/`generate_monthly_receipts`. Re-checking it with
a second query beforehand would either drift from those engines' own
rules over time or just duplicate them — exactly what the "do not
duplicate business logic" constraint rules out.

## Database entity

Two new tables, both additive — `rental_contracts`, `lease_agreements`,
`invoices`, and `rental_payment_installments` are **not modified**.

### `rent_cycles`
| Column | Notes |
|---|---|
| `id`, `uuid`, `status`, `created_at`, `updated_at`, `deleted_at`, `created_by`, `updated_by` | Standard audit columns every table in this system has |
| `cycle_number` | `RC-000001`, sequential, unique |
| `month`, `year` | The billing period this cycle covers |
| `start_date`, `due_date`, `closing_date` | `closing_date` is set when the cycle is closed |
| `cycle_status` | draft / generated / printed / distributed / collecting / partially_collected / completed / closed / cancelled |
| `property_ids` | Optional JSON array — scopes the cycle to a subset of the portfolio, mirrors `generate_bulk_invoices`' own `property_ids` param. `null` = whole portfolio |
| `notes`, `cancellation_reason` | Free text |
| `generated_at`, `closed_at` | Timestamps for the two key transitions |

### `rent_cycle_records`
One row per lease the cycle actually touched. `UNIQUE(cycle_id, rental_contract_id)`.

| Column | Notes |
|---|---|
| `cycle_id` | FK → `rent_cycles.id`, `ON DELETE CASCADE` |
| `rental_contract_id` | FK → `rental_contracts.id` — the lease this record is for. **Not** a new column on `rental_contracts` itself; the reference goes the other way |
| `invoice_id` | FK → `invoices.id`, nullable until the invoice step runs |
| `installment_id` | FK → `rental_payment_installments.id`, nullable until the receipt step runs |
| `amount`, `due_date` | Captured at generation time |
| `record_status` | generated / skipped / failed |
| `skip_reason` | Set when `record_status` is `skipped`/`failed` |

Read-only display fields (`tenant_display_name`, `property_title`,
`building_title`, `unit_number`, `invoice_number`, `invoice_status`,
`receipt_number`) are computed `@property` accessors on the
`RentCycleRecord` model — same pattern `MaintenanceRequest` and
`RentalContract` already use for their own display fields — not stored
columns, so they can never drift from the underlying `Invoice`/
`RentalPaymentInstallment` rows.

Migration: `app/alembic/versions/0018_rent_cycle_engine.py`.

## API endpoints

All under `/api/v1/rent-cycles`, permission-gated the same way every
other module in this codebase already is (`rent_cycles.view` /
`.create` / `.edit`, added to the `MODULES` catalog in `seed.py` —
matches how `leases.py` gates activate/terminate/renew all under a
single `leases.edit` rather than one permission per transition):

| Method & path | Permission | Notes |
|---|---|---|
| `POST /rent-cycles` | `rent_cycles.create` | Rejects a second cycle for the same `(year, month)` — 409 |
| `GET /rent-cycles` | `rent_cycles.view` | Paginated, filterable by `year`/`cycle_status` |
| `GET /rent-cycles/{id}` | `rent_cycles.view` | Full detail incl. every `RentCycleRecord` |
| `POST /rent-cycles/{id}/generate` | `rent_cycles.edit` | Body: `{"force": bool}`. Safe no-op if already generated and `force` is omitted. `force: true` on an already-generated cycle additionally requires the caller to be a superuser (403 otherwise) — enforced both in the router and in `RentCycleValidator.validate_can_generate` |
| `POST /rent-cycles/{id}/close` | `rent_cycles.edit` | Body: `{"notes": str?}` |
| `POST /rent-cycles/{id}/reopen` | `rent_cycles.edit` | Only from `closed` |
| `POST /rent-cycles/{id}/cancel` | `rent_cycles.edit` | Body: `{"reason": str}` — required, from any non-terminal state |
| `GET /rent-cycles/dashboard/summary` | `rent_cycles.view` | Cycle counts by status + the current `(year, month)` cycle's live collection snapshot |

Every write endpoint logs to both `ActivityLog` and `AuditLog` via the
existing `AuditService` (User, Timestamp, Action, Affected Cycle — via
`entity_type="rent_cycle"` / `entity_id=<cycle id>`), the same as every
other module.

## Developer guide

Package layout (`app/business_workflows/rent_cycle/`):

```
rent_cycle_service.py      Public facade — what the router calls
rent_cycle_validator.py    Every legal-transition rule, table-driven
rent_cycle_scheduler.py    Dates + cycle_number, no business rules
rent_cycle_generator.py    Calls the two existing engines, writes RentCycleRecord
rent_cycle_closer.py       Collection-progress calc + close/reopen/cancel
rent_cycle_exceptions.py   HTTPException subclasses, one per failure mode
```

To add a new lifecycle state or transition: add the status constant to
`RentCycleStatus` in `app/models/rent_cycle.py`, add it to the relevant
`*_FROM` set in `rent_cycle_validator.py`, and (if it affects the
auto-computed collection states) extend `RentCycleCloser.refresh_status`.
No other file needs to change — this mirrors how
`MaintenanceService.ALLOWED_TRANSITIONS` keeps the maintenance status
machine in one place.

To generate a cycle from Python directly (e.g. a script or a future
scheduler job — see "Not done in this phase" below):

```python
from app.business_workflows.rent_cycle.rent_cycle_service import RentCycleService

service = RentCycleService(db)
cycle = service.create_cycle({"month": 7, "year": 2026}, actor_id=admin_id)
cycle, result = service.generate(cycle.id, actor_id=admin_id, is_admin=False)
print(result.invoices_generated, result.receipts_generated)
```

### Testing

`backend/tests/test_rent_cycle_engine.py` — creation, duplicate
prevention, generation (incl. reuse of the existing engines and
duplicate-record prevention), regeneration authorization, close/reopen/
cancel transitions, collection-progress recalculation, the dashboard,
the full API workflow, and permission enforcement (including isolating
"requires `rent_cycles.edit`" from "requires superuser for
`force=true`" as two separate checks).

## Not done in this phase (by design)

- **No scheduler wiring.** Cycle creation and generation are on-demand
  via the API, same as every other on-demand batch operation in this
  codebase (`run_maintenance_sweep`, `generate_bulk_invoices`,
  `generate_monthly_receipts` itself). Wiring `POST /rent-cycles` +
  `POST /rent-cycles/{id}/generate` to a monthly cron/Azure Function
  timer trigger is a natural next step — see
  `docs/phase3-renewal-reminders.md` for the existing note on doing
  this for the other sweep endpoints.
- **`printed`/`distributed` are not automated.** Both statuses exist in
  `RentCycleStatus` (per spec) and are legal `cycle_status` values, but
  nothing in this phase transitions a cycle into them automatically —
  there's no "print" or "distribute" action/endpoint yet, since the
  spec didn't describe what those operations should actually *do*
  beyond changing the status. `RentCycleValidator`'s `GENERATABLE_FROM`
  and `CLOSABLE_FROM` sets already include them so adding the two
  endpoints later (each just setting `cycle_status` and logging) is a
  small, additive change.
