# Permissions Matrix — Phase 1

Permission codes follow `module.action`. Superusers (`is_superuser = true`)
bypass all checks. Non-superusers need the exact code on their assigned role.

## Modules & actions seeded in Phase 1

| Module | view | create | edit | delete |
|---|---|---|---|---|
| users | ✅ | ✅ | ✅ | ✅ |
| roles | ✅ | ✅ | ✅ | ✅ |
| branches | ✅ | ✅ | ✅ | ✅ |
| countries | ✅ | ✅ | ✅ | ✅ |
| cities | ✅ | ✅ | ✅ | ✅ |
| currencies | ✅ | ✅ | ✅ | ✅ |
| company | ✅ | – | ✅ | – |
| settings | ✅ | – | ✅ | – |
| audit | ✅ | – | – | – |
| owners | ✅ | ✅ | ✅ | ✅ |
| leases | ✅ | ✅ | ✅ | ✅ |
| properties | ✅ | ✅ | ✅ | ✅ |
| tenants | ✅ | ✅ | ✅ | ✅ |
| rentals | ✅ | ✅ | ✅ | ✅ |
| financial | ✅ | ✅ | ✅ | ✅ |
| maintenance | ✅ | ✅ | ✅ | ✅ |
| accounting | ✅ | ✅ | ✅ | ✅ |
| reports | ✅ | ✅ | ✅ | ✅ |

(`company` and `settings` are singleton/global resources, so only `view`
and `edit` apply. `audit` is read-only by design. Phase 5 Unit Management —
Floors, unit fields, parking/storage linkage — reuses the `properties`
module rather than adding a new one, since floors and units are
sub-resources of the Property aggregate. Blacklist and Rating actions on
tenants are gated behind `tenants.edit` rather than a separate permission,
consistent with how lease status transitions in Phase 3 reused
`leases.edit`. Rental contract status transitions — activate, terminate,
renew — and payment schedule management reuse `rentals.edit` for the same
reason. Phase 8's Transfers, Invoice send/cancel, and Record Payment
actions all reuse `financial.create`/`financial.edit` — no separate
permissions were added for each financial action type. Phase 9's status
transitions on Maintenance Requests — assign/start/hold/resume/complete/
cancel — and Materials/Labor Cost/Photo management all reuse
`maintenance.edit`. Staff is additionally granted `maintenance.create` (but
not `.edit`) so front-line staff can report issues without being able to
otherwise manage the maintenance workflow. Phase 10's Accounting module is
deliberately more restricted than other modules — Staff has no
`accounting.*` permission at all, and Branch Manager gets `accounting.view`
only, since chart-of-accounts/journal-entry access is typically limited to
accounting staff and administrators rather than general branch operations.
Phase 11's `reports` module only meaningfully uses `.view` — every report
endpoint is a read-only GET, so `.create`/`.edit`/`.delete` exist for
schema consistency but are never checked. Both Branch Manager and Staff
get `reports.view`, consistent with their existing `financial.view`
access, since these are aggregate/summarized views rather than raw
ledger access.)

## Seeded system roles

| Role | Permissions |
|---|---|
| **Administrator** | All permissions (`is_superuser = true`, bypasses checks entirely) |
| **Branch Manager** | `users.view`, `branches.view`, `countries.view`, `cities.view`, `currencies.view`, `company.view`, `settings.view`, `owners.view`, `owners.create`, `owners.edit`, `leases.view`, `leases.create`, `leases.edit`, `properties.view`, `properties.create`, `properties.edit`, `tenants.view`, `tenants.create`, `tenants.edit`, `rentals.view`, `rentals.create`, `rentals.edit`, `financial.view`, `financial.create`, `financial.edit`, `maintenance.view`, `maintenance.create`, `maintenance.edit`, `accounting.view`, `reports.view` |
| **Staff** | `branches.view`, `countries.view`, `cities.view`, `currencies.view`, `company.view`, `owners.view`, `leases.view`, `properties.view`, `tenants.view`, `rentals.view`, `financial.view`, `maintenance.view`, `maintenance.create`, `reports.view` |

System roles (`is_system_role = true`) cannot be renamed, disabled, or
deleted — this is enforced server-side in `RoleService`, not just hidden in
the UI, so it can't be bypassed via direct API calls.

## Extending permissions in future phases

Every new module (Properties, Lease Agreements, Tenants, Subleases, …)
should register `module.view / create / edit / delete` (and any custom
actions, e.g. `leases.approve`) in `seed.py`'s `MODULES` list, then assign
them to the appropriate roles. No code changes are needed elsewhere — the
`PermissionChecker` dependency and the `RoleService` permission editor UI
already work generically against the `permissions` table.

## Property Profit Center extension (post-Phase 11)

No new permission module was added. The 7 new `/properties/{id}/reports/*`
and `/properties/{id}/financial-dashboard` endpoints reuse the permission
of whichever existing module actually owns the underlying data they
report on: P&L, Expense, and Financial Dashboard reuse Phase 11's
`ReportsService` and require `reports.view`; Cash Flow, Income Statement,
Ledger, and Balance Summary reuse Phase 10's `AccountingReportService`
and require `accounting.view` — identical to their portfolio-wide
counterparts under `/accounting/reports/*` and `/reports/*`. Staff's
access is therefore unchanged: still full access to the operational
reports, still no access to the GL-grade ones.

## Enterprise Dashboard extension (post-Phase 11)

No new permission module or endpoint. The Enterprise Dashboard page
(`/enterprise-dashboard`) calls the exact same `GET
/reports/analytics/dashboard` endpoint as the underlying `dashboard_
analytics` service method, so it's gated by the existing `reports.view`
permission — same access as the original Dashboard Analytics view.

## Enterprise Reporting extension (post-Phase 11)

No new permission module. `reports.create`, `reports.edit`, and
`reports.delete` already existed as permission rows since Phase 11
(seeded for schema consistency, never assigned to a role) — this phase
completes that by assigning all three to Branch Manager, so they can
create/edit/delete their own scheduled report exports. Staff keeps
`reports.view` only: full read/export access to every report (all 10
categories, PDF/Excel export), no schedule management. Running a
schedule that already exists (`run-now`) is also gated by
`reports.edit`, consistent with schedules being a mutating action on a
saved configuration.

## Rental Receipt Module (post-Phase 11)

No new permission module — this was an explicit Phase 1 decision (see
`docs/rental-receipt-module.md`). Generate/search/view/print reuse
`rentals.*`; **Confirm Payment reuses `financial.edit`**, not
`rentals.edit`, deliberately matching the existing precedent set by
`POST /financial/invoices/{id}/record-payment` — both actions create a
`Transaction` and post to the GL, so both are gated the same way.
Administrator and Branch Manager already have every permission this
module needs; Staff (which only has `rentals.view` and `financial.view`
— no `.create`/`.edit` on either) can view, search, and print receipts,
but can neither generate a month's receipts (`rentals.create`) nor
confirm a payment (`financial.edit`) — the same access boundary Staff
already has for rental contracts and invoices respectively.

## Rent Billing Engine (post-Phase 11)

No new permission module — every action reuses `financial.*`, already
covering Invoices from Phase 8. `financial.create` gates bulk
generation; `financial.edit` gates approve/void/cancel/record-payment/
deliver; `financial.view` gates search/print/print-data (printing and
previewing are read-mostly operations — print does increment
`print_count`, but that's audit tracking, not a business-state change,
consistent with how the Rental Receipt Module's print tracking is also
gated by the view-adjacent permission rather than edit). The QR
verification endpoint intentionally has **no** permission check at all
— it's meant to be reachable by anyone holding a printed invoice.
