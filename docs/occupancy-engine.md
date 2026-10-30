# Occupancy & Unit Lifecycle Engine (Phase 18)

## Pre-implementation analysis

| Area | Finding |
|---|---|
| **Current unit status** | `Property.availability_status` (Phase 4) — a plain stored column, defaulting to `available`. |
| **Who sets it** | Exactly two call sites, both in `RentalService`: `activate_contract()` sets it to `"leased"`, `terminate_contract()` sets it back to `"available"`. No other code path ever touches it — maintenance, reservations, and every other status this phase asks for have never been wired to it at all. |
| **Who reads it** | `PropertyRepository.unit_availability_counts()` — a plain `GROUP BY Property.availability_status` — feeding `PropertyService._aggregate_container()`, which backs the existing `get_building_summary()`/`get_property_summary()`. |
| **Reservations** | No `Reservation` entity or workflow exists anywhere in this codebase. `"reserved"` is a dead enum value with no code path that ever sets it. |
| **Notice period / vacating soon** | No concept of a tenant-initiated move-out notice exists. `RentalContract.renewal_notice_days` + `is_expiring_soon` (Phase 3) is about *renewal reminders*, not a distinct "about to vacate" signal. |
| **Existing "Prevent multiple active leases" enforcement** | **None.** `activate_contract()` had no check at all for another already-active contract on the same unit — a real, pre-existing gap, not something this phase introduced. |

**Conclusion:** the spec's framing — "the current system stores unit status... replace this with a dynamic engine... never depend on manual status updates" — is accurate. `availability_status` is exactly the anti-pattern described, updated in only two places and silently going stale everywhere else (a maintenance request opening, a lease simply expiring without anyone calling `terminate`, etc. never touch it).

## Conflicts found, and the safest solution for each

### Conflict 1 — six of the eleven statuses have no data source anywhere in this codebase

Available, Occupied, Notice Period, Vacating Soon, and Under Maintenance can all be derived from data that already exists (`RentalContract`, `MaintenanceRequest`). **Reserved, Cleaning, Inspection, Blocked, Renovation, and Inactive cannot** — there is no reservation system, no cleaning-service module, no renovation-tracking module, and no "unit taken off market" flag anywhere in this codebase.

**Safest solution:** rather than either (a) building out six new full subsystems no one asked for — a real Reservation module alone would need holds, deposits, expiry, and its own approval flow, wildly out of scope for "Do not implement Analytics or Profit Center in this phase" — or (b) silently pretending those six statuses don't exist, a single new, small, generic table (`UnitOccupancyOverride`) represents an explicit administrative decision that a unit is in one of these states right now, with a reason, who set it, and an optional expiry. It's honest about what it is: a manual override, for the one part of the spec that has no other source of truth to be automatic *about*. Every other status is still fully automatic.

### Conflict 2 — "Notice Period" and "Vacating Soon" need one new fact that didn't exist

These are listed as two distinct statuses, but the only existing signal (`is_expiring_soon`, derived from `end_date`) can only produce one of them. The other — "the tenant has formally said they're leaving" — has no field anywhere.

**Safest solution:** one new nullable column, `RentalContract.move_out_notice_date` (migration `0022`). Purely additive; every existing contract row is unaffected (defaults to `NULL`, meaning "no notice given," which is the correct behavior for 100% of contracts that predate this phase).

### Conflict 3 — audit trail vs. "never store the status"

The spec asks for both "never depend on manual status updates" (implying status should be *computed*, not stored) **and** "every status change must be recorded" (implying there must be a discrete, loggable event when a change happens). A purely computed value has no natural "it changed" moment to hook.

**Safest solution:** the engine's read path (`compute_unit_status`/`compute_bulk`) never writes anything — every `GET` endpoint always reflects the true current state, live, with zero staleness risk. Auditing is a *separate*, explicit action: `recalculate_and_log()` computes the current status, compares it against the last **logged** status for that unit, and writes one `OccupancyStatusHistory` row only if they differ. This is called by `POST /occupancy/recalculate` and by the override/notice endpoints themselves right after they act (so an explicit staff action is reflected in the audit trail immediately, not just on the next sweep).

### Conflict 4 — layering: services must never depend on business_workflows

Preventing "multiple active leases on the same unit" needs to happen *inside* `RentalService.activate_contract()` to actually block the action — but `business_workflows/` sits **above** `app/services/`, and this codebase's own established rule (see `app/business_workflows/__init__.py`) is that services never import from business_workflows, only the reverse. Hooking `RentalService` directly into `OccupancyValidator` would invert that.

**Safest solution:** the count query itself (`OccupancyDataRepository.count_other_active_contracts`) lives in `app/repositories/` — a shared lower layer both `app/services/` and `business_workflows/` may depend on. `RentalService.activate_contract()` and `OccupancyValidator.validate_no_other_active_lease()` both call the *same* repository method; neither depends on the other's package. One implementation, correct layering, no duplication.

## New database objects

| Table/column | Purpose |
|---|---|
| `rental_contracts.move_out_notice_date` | Nullable `Date` — see Conflict 2. |
| `unit_occupancy_overrides` | Administrative overrides for the six OVERRIDABLE statuses — see Conflict 1. Never deleted; cleared by setting `cleared_at`/`cleared_by`/`clear_reason` on the same row (same "never delete, only supersede" pattern as `OwnerLedgerEntry` reversals). |
| `occupancy_status_history` | The audit trail — see Conflict 3. One row per logged *change*, not one row per recalculation. |

`properties.availability_status` is **untouched** — left in place for backward compatibility with `PropertyService`'s existing building-summary aggregation, which still reads it. The new engine never reads or writes it. A future cleanup phase could migrate that older aggregation onto the new engine and then deprecate the column, but that's out of scope here (no existing functionality was asked to change).

## The engine: how status is computed

`OccupancyEngine.compute_unit_status(property_id)` — priority order, highest wins:

1. **Active administrative override** (Inactive > Blocked > Renovation > Cleaning > Inspection > Reserved)
2. **Open `MaintenanceRequest`** → Under Maintenance (matches the spec's own example literally — this outranks even an active lease; see the trade-off note in `occupancy_engine.py`'s module docstring)
3. **Active lease with `move_out_notice_date` set** → Notice Period
4. **Active lease, `is_expiring_soon`, no notice given** → Vacating Soon
5. **Active lease, nothing else** → Occupied
6. **Nothing else applies** → Available (the true default)

`compute_bulk()` is the same logic batched — 3 queries total for any number of units, used by every dashboard/building-summary/units-list endpoint (`compute_unit_status()` is the single-unit convenience version).

## Dashboard & Building Summary

`GET /occupancy` — portfolio-wide: total/occupied/vacant/reserved/maintenance/notice-period/vacating-soon units, occupancy %, vacancy %, and a full breakdown by every status.

`GET /occupancy/buildings` (optionally `?building_id=`) — per building: occupancy %, vacancy %, **average rent** (mean `rent_amount` across that building's *active* contracts — deliberately not `Property.rent_price`, the asking price, since most currently-occupied units won't have one set), active contracts, expiring contracts, open maintenance count. Reuses `RentalContractRepository`/`MaintenanceRequestRepository`'s existing count methods — only the occupancy figures themselves come from the new engine instead of the old stored-column count.

## Validations

| Rule | Where enforced |
|---|---|
| Multiple active leases on same unit | `RentalService.activate_contract()` (now) + `OccupancyValidator` (for this module's own future write paths) — same repository method, see Conflict 4 |
| Reservation conflict | Can't set `reserved` on a unit that's currently Occupied or in Notice Period |
| Maintenance conflict | Can't set `reserved`/`cleaning`/`inspection` while an open `MaintenanceRequest` exists — resolve it first rather than let an override silently mask it |
| Duplicate occupancy state | Can't set the same override status twice while one is already active |

## API

| Method & path | Permission | Notes |
|---|---|---|
| `GET /occupancy` | `occupancy.view` | Portfolio dashboard |
| `GET /occupancy/buildings` | `occupancy.view` | All buildings, or one via `?building_id=` |
| `GET /occupancy/units` | `occupancy.view` | Paginated, filterable by `building_id`/`occupancy_status` |
| `POST /occupancy/recalculate` | `occupancy.edit` | The audit sweep — see "Automatic" note below |
| `POST /occupancy/units/{id}/override` | `occupancy.edit` | Added — otherwise 6 of 11 statuses are unreachable |
| `POST /occupancy/overrides/{id}/clear` | `occupancy.edit` | Added |
| `POST /occupancy/contracts/{id}/notice` | `occupancy.edit` | Added — otherwise Notice Period is unreachable |
| `GET /occupancy/units/{id}/history` | `occupancy.view` | Added — per-unit audit trail |

### "Automatic" and the recalculate sweep, honestly

Every `GET` endpoint is always accurate and live — that part needs no scheduler at all. The **audit trail** (`occupancy_status_history`) only grows when `POST /occupancy/recalculate` runs, or when an override/notice endpoint is called directly (which triggers the same log-if-changed check immediately). This codebase has no background job runner anywhere (see `LeaseWorkflowService`'s renewal sweep and `NotificationWorkflowService`'s daily sweep — both already documented the same way): a real deployment should point an external cron at `POST /occupancy/recalculate` every few minutes. This is the exact same honest pattern already established for lease renewal reminders, applied consistently here rather than inventing a different story for this module.

## Testing

`backend/tests/test_occupancy_engine.py` — status computation for every reachable status (available, occupied, under_maintenance including its priority over an active lease, notice_period, vacating_soon, and the override statuses), every VALIDATIONS rule (reservation conflict, maintenance conflict, duplicate occupancy state, multiple active leases), the dashboard, building summary (including average rent), the recalculate sweep's diff-based audit logging (first sweep logs, no-change sweep logs nothing, a real change logs exactly one entry), per-unit history, activity-log auditing on override actions, the full API workflow, and permission enforcement.

## Explicitly out of scope for this phase

- **Analytics or Profit Center** — per the spec's own instruction.
- **A real Reservation/Cleaning/Renovation subsystem** — the override table is the honest, minimal-footprint stand-in; see Conflict 1.
- **A real background scheduler** — consistent with every other "sweep" already in this codebase; see the recalculate section above.
- **Migrating `PropertyService`'s existing building-summary aggregation onto the new engine** — that older code path is untouched and still works exactly as before; this phase adds the new engine alongside it rather than rewriting existing, working functionality that wasn't asked to change.
