# Dashboard Consolidation & Currency/Country UI Simplification

## Dashboard: two real pages → one

`DashboardPage.tsx` (`/dashboard`, no special permission) and
`EnterpriseDashboardPage.tsx` (`/enterprise-dashboard`, `reports.view`)
were genuinely two different pages pulling from two different endpoints
— not accidental duplication, but confusing to navigate ("which one is
*the* dashboard?").

**Decision (confirmed in conversation): merge into one, retire Enterprise
Dashboard.** `/dashboard` now carries everything from the requested spec:

- **Top Summary Cards**: Total Buildings, Total Apartments, Occupied
  Apartments, Vacant Apartments, Active Contracts, Expiring Contracts,
  Total Tenants — computed by composing three already-existing,
  already-tested services rather than re-deriving any of this math a
  second time: `OccupancyService.get_dashboard()` (Phase 18) for the
  apartment/occupancy counts, `RentalContractRepository.dashboard_counts()`
  (Phase 7) for active/expiring contract counts, and a `Property` count
  filtered to `parent_property_id IS NULL` for buildings.
- **Property Overview**: `OccupancyService.get_buildings()` (Phase 18)
  already returns per-building occupancy %, unit counts, and active/
  expiring contract counts — reused as-is, not re-implemented.
- **Contract Management**: recent contracts + the same expiring-soon
  list `RentalContractRepository.dashboard_counts()` already computes.
- **Tenant Overview**: 5 most recently created tenants.
- **Quick Actions**: Add Building / Add Apartment / Create Contract /
  Add Tenant / Print Reports. The first three navigate to their list
  page with `?new=true`, which now auto-opens that page's existing
  create modal (`PropertiesPage.tsx`, `RentalsPage.tsx`,
  `TenantsPage.tsx` each gained a 2-line `useSearchParams` check for
  this — no new modal, no duplicated form).

The previous system-admin-oriented widgets (users, roles, branches, GL
trial-balance variance, cash balance, unread notifications) are **not
deleted** — they're collapsed into a "More system stats" `<details>`
section beneath the primary cards, so daily property-management tasks
aren't competing for attention with system administration, per "avoid
information overload," without actually removing anything someone
might still rely on.

`EnterpriseDashboardPage.tsx`'s deeper trend charts (revenue over time,
occupancy trends, etc., from `GET /reports/analytics/dashboard`) aren't
lost — that data was already duplicated at `/reports`, which has the
same chart types. The route to `/enterprise-dashboard` is commented out
(not deleted) in `App.tsx`/`Sidebar.tsx`, so it's a one-line revert if
ever needed.

## Currency & Country: UI simplified, nothing in the database touched

**This was the important correction made before touching anything**:
the original request asked to delete the Currency and Country
*database tables*. Investigation showed that would be actively
destructive:

- `currency_id` is a real FK on **6 core models** — `Invoice`/
  `Transaction` (Financial), `LeaseAgreement`, `RentalContract`,
  `MaintenanceContract`, and `Owner` — and `Currency` itself carries
  `exchange_rate_to_base`/`is_base_currency`, i.e. genuine multi-
  currency support, not a decorative dropdown.
- `City.country_id` is a **required (NOT NULL)** FK to `Country` —
  deleting Country would make every City row, and everything that
  references a City (Property, Owner, Tenant addresses), invalid.

**What was actually done instead** (confirmed as the safe alternative):
only the standalone *management* screens were disabled —
`CurrenciesPage.tsx` (`/currencies`) and `CountriesPage.tsx`
(`/countries`), plus their Sidebar entries. `CitiesPage.tsx` (`/cities`)
stays, since a single-country operation still benefits from picking
which city a property/owner/tenant is in. The Company Profile page's
one "default currency" and "default country" pickers
(`CompanyProfilePage.tsx`) are untouched — that's the correct place for
"the system uses one configured currency/country," which is exactly
what was asked for.

No model, migration, schema, or backend endpoint was touched for this
part at all — it's a pure navigation/routing change. Both routes are
commented out (not deleted) in `App.tsx`, with the same one-line-revert
note as the dashboard change above.

## Self-audit

- **Broken links**: grepped for any other in-app link pointing at
  `/currencies`, `/countries`, or `/enterprise-dashboard` after removing
  their nav entries — none found; nothing in the app links to them
  except the (now-commented) routes themselves.
- **Duplicate pages**: none created. No new page duplicates an existing
  one's data source.
- **Unused DB fields**: none created or orphaned — this change didn't
  touch the database at all.
- **Existing data**: unaffected — Currency/Country/City rows, and every
  FK pointing at them, are completely untouched; only two admin screens
  became unreachable via the UI.
- **Not tested by running the app** (no network access in this
  environment to install dependencies or start the servers) — every
  file was syntax-checked and every reused service/field name verified
  against its actual source. Please click through the new `/dashboard`
  and confirm: the 7 top cards show sensible numbers, each Quick Action
  correctly opens its target page's create form, and that
  `/currencies` / `/countries` / `/enterprise-dashboard` correctly
  return "not found" (routing) while `/cities` and Company Profile's
  currency/country pickers still work normally.
