# Archive extension (post-Phase 3 Business Logic Review)

## What was missing

Every table already had a `status` column with `RecordStatus.ARCHIVED`
defined (`app/models/base.py`) — but it was only ever reached as a side
effect of `soft_delete()`, which sets `status='archived'` **and**
`deleted_at` together, as one combined action. There was no way to mark
something "done/historical, keep it out of the main list" while it
stayed a fully normal, visible-everywhere-else record — "archive" and
"delete" were, in practice, the exact same button.

## What was added

`BaseRepository.archive()` / `.unarchive()` — new, alongside the
existing `soft_delete()` / `restore()` (both untouched, unchanged
behavior). `archive()` only ever sets `status`; it never touches
`deleted_at`. An archived record:
- is excluded from the default list view (opt-in via
  `?include_archived=true`, or the "Show Archived" checkbox in the UI)
- remains fully visible in direct lookups, reports, referential
  integrity checks, and every other place that only filters on
  `deleted_at` (i.e. everywhere except the three list endpoints below)

Wired into the two areas requested: **Contracts** (`LeaseAgreement` —
Owner→Company, and `RentalContract` — Company→Tenant) and
**Properties**. Each gets `POST /{id}/archive`, `POST /{id}/unarchive`,
and an `include_archived` query param on its list endpoint (default
`false`). No new permission — reuses the existing `*.edit` permission
for archive/unarchive, same as every other status-changing action on
these entities.

## Why this is safe

As of this change, no existing record can already be "archived but not
deleted" — `RecordStatus.ARCHIVED` was previously unreachable any other
way, so every property/lease/contract in an existing database is either
`status='active'` or already soft-deleted (and therefore already
invisible everywhere). Turning on the new `include_archived=False`
default filtering therefore changes **zero** existing query results on
day one; it only starts doing something the first time someone actually
clicks the new Archive button.

## Frontend

- **Archive / Unarchive button** on the Property, Lease, and Rental
  Contract detail pages, next to Delete — gated by the same `*.edit`
  permission already used for every other action there.
- **"Show Archived" checkbox** on the Properties, Leases, and Rental
  Contracts list pages.
- Archived items show an **"Archived"** badge in list rows (Properties
  already showed the base `status` field directly via `StatusBadge`;
  Leases/Rental Contracts show it as a small badge next to their
  `contract_status` badge, since those tables display `contract_status`
  as the primary badge).

No existing page, endpoint, or soft-delete/restore behavior was
changed.
