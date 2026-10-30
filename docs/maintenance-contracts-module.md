# Maintenance Contracts extension (post-Phase 9)

## What was missing

Phase 9 (Maintenance) models *reactive* maintenance only: something
breaks, staff or a tenant files a `MaintenanceRequest`, it gets assigned,
worked, and closed. There was no way to record that the company has a
**recurring/annual service contract** with a contractor — e.g. quarterly
elevator inspections, semi-annual AC servicing — with its own term, cost,
and renewal date. `elevator` and `hvac` already existed as
`MaintenanceRequest.category`/`Contractor.specialty` values, but only as
labels on one-off tickets, never as a contract entity.

## Design

`MaintenanceContract` (new table, migration `0024`) is deliberately the
same shape as `LeaseAgreement` (Phase 3) and `RentalContract` (Phase 7) —
this codebase already has two working examples of "contract with a
draft → active → (expired | terminated | renewed) status machine and a
renewal-creates-a-new-row pattern," so a fourth contract-like entity
reuses that shape rather than inventing a new one.

Two concerns are tracked independently, because they answer different
questions:
- **Contract expiry** (`end_date`, `renewal_notice_days`,
  `is_expiring_soon`) — "is this annual agreement about to lapse?"
- **Service due date** (`next_service_due_date`, `visit_frequency`,
  `is_service_due_soon` / `is_service_overdue`) — "is the elevator
  technician's next quarterly visit coming up?", independent of how much
  of the year-long contract term remains.

`service_type` reuses the exact same vocabulary as
`MaintenanceRequest.category` (`elevator`, `hvac`, ... — see
`VALID_CATEGORIES` in `app/schemas/maintenance.py`) rather than a new
taxonomy.

## What's additive vs. new

- **New**: `maintenance_contracts` table, its repository/service/schemas,
  and nine new endpoints under `/maintenance/contracts/*`.
- **Additive only** on the existing Phase 9 table: one nullable column,
  `maintenance_requests.maintenance_contract_id`, so an individual work
  order can optionally be linked back to "this was performed under
  contract MTC-000004." Every existing and future ad-hoc/reactive
  request is unaffected (`NULL` by default); nothing about the reactive
  workflow changed.
- **No new permission module** — every endpoint reuses the existing
  `maintenance.view/create/edit/delete` permissions, exactly like every
  other Phase 9 sub-resource (materials, labor costs, photos).

## Renewal reminders & service-due notifications

Same on-demand sweep pattern as Phase 3's lease renewal reminders (no
background job scheduler exists in this stack): `POST
/maintenance/contracts/maintenance/run` does three things, idempotently:
1. Auto-expires `active` contracts whose `end_date` has passed.
2. Sends an in-app notification to every superuser for contracts entering
   their `renewal_notice_days` window (mirrors
   `docs/phase3-renewal-reminders.md` exactly).
3. Separately, sends a notification for contracts whose
   `next_service_due_date` is within 14 days or already overdue — this is
   the elevator/AC-specific concern this extension exists for, and is
   deliberately not the same signal as "the contract is expiring."

In production, wire this endpoint to a daily cron / Azure Function timer
trigger, the same honest limitation already documented for the Phase 3
sweep — no scheduler was added here either, to stay consistent with the
rest of the codebase rather than solving that gap partially for one
module.

## Renewal

`POST /maintenance/contracts/{id}/renew` creates a **new** contract row
(so the old contract's history and any linked maintenance requests stay
intact) and marks the old one `renewed`, linked via
`renewed_from_contract_id` — identical mechanics to
`LeaseService.renew_lease`.

## Service visits

`POST /maintenance/contracts/{id}/log-visit` records that the scheduled
visit happened and advances `next_service_due_date` by one
`visit_frequency` step. This is deliberately lightweight (a date + free
text note via the activity log) rather than a full visit-report entity —
if a future need arises for structured per-visit records (checklist
items, signed reports, photos), `MaintenanceRequest` with
`maintenance_contract_id` set is the natural place to log that specific
visit as a proper work order, reusing Phase 9's materials/labor/photos
machinery instead of duplicating it here.

## Sample data

`seed.py` adds one elevator contractor (`CON-000002`, SkyLift Elevator
Services) and two active contracts: an annual elevator maintenance
contract (`MTC-000001`, quarterly visits) on the seeded building
property, and an annual AC maintenance contract (`MTC-000002`,
semi-annual visits) on the seeded villa, using the existing HVAC
contractor (`CON-000001`).

## Frontend

New page at `/maintenance/contracts` (linked from the Maintenance page's
header, alongside the existing "Contractors & Technicians" link):
listing with search/status/service-type filters, a create modal, and
per-row actions (Activate / Log Visit / Renew / Terminate) gated by the
same `maintenance.create`/`maintenance.edit` permissions already used
elsewhere in this module. No existing maintenance page, route, or
component was modified beyond adding this one new button.
