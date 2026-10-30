# Phase 2.0 — Property Structure & Unit Management Enhancement

Changelog for this delivery. Everything below is additive to the existing
Owner → Property → Floors → Units → Rental Contract → Tenant hierarchy
(Phase 4/5) — no existing tables, models, APIs, or UI components were
duplicated. See inline comments at each change site for the full
reasoning.

## 1. Property Types
- Added `commercial_building`, `commercial_complex`, `mixed_use` to
  `PropertyType` (`backend/app/models/property.py`,
  `backend/app/schemas/property.py`).
- `PropertyType.CONTAINER_TYPES` / `RESIDENTIAL_UNIT_TYPES` /
  `COMMERCIAL_UNIT_TYPES` added so the type classification lives in one
  place instead of being hardcoded per feature.

## 2. Building / Villa characteristics
- New nullable columns on `Property`: `elevators`, `parking_spaces_count`,
  `garden`, `swimming_pool`, `maid_room`.
- Migration: `backend/app/alembic/versions/0016_property_structure_enhancement.py`.

## 3. Automatic calculations & Property Summary
- `PropertyService._aggregate_container()` — shared computation behind
  both the existing `building-summary` endpoint and the new
  `PropertySummaryOut`, so the numbers can't disagree.
- `PropertyDetailOut.summary` is now populated automatically for any
  container-type property: occupancy rate, residential/commercial split,
  active/expired/expiring-soon contracts, monthly revenue/expenses/net
  profit (reuses `ReportsService.property_financial_dashboard`).

## 4. Main Dashboard
- `GET /properties/dashboard/summary` now also returns
  `total_buildings`, `total_villas`, `total_commercial_properties`,
  `total_warehouses`, `total_lands`, `total_units`, `occupied_units`,
  `vacant_units`, `occupancy_rate`.
- `frontend/src/pages/PropertiesPage.tsx` — widget grid expanded to
  surface all of the above.

## 5. Reports
- New `GET /reports/units` — covers Building Units Report, Villa Units
  Report (`?property_id=`), Unit Status Report, and Unit Availability
  Report in one endpoint (mirrors how Vacancy/Occupancy already share one
  query pattern). Wired into the existing export/schedule dispatch
  (`REPORT_TYPES`, `generate_report`, `report_to_document`) — gets
  PDF/Excel export and scheduling for free.
- `frontend/src/pages/ReportsPage.tsx` — new "Units" tab with a
  building/villa scope filter.

## 6. Search & Filters
- `GET /properties` gained a `floor_id` filter (was completely missing).
- Free-text `search` now also matches `unit_number`.
- `PropertiesPage.tsx` toolbar gained Building/Villa and cascading Floor
  filter dropdowns.

## 7. Performance
- Three indexes added that were missing despite being active filter
  columns on `GET /properties`: `parent_property_id`, `branch_id`,
  `city_id` (same migration `0016`).

## 8. Bugs fixed along the way (not originally in scope, but required for
   correctness once the above shipped)
- `NON_LEASABLE_TYPES` (`reports_repository.py`) only excluded
  `"building"` from vacancy/occupancy math — the new
  `commercial_building`/`commercial_complex` container types would have
  silently miscounted as vacant units. Fixed.
- `rental_service.py::get_receipt_document` referenced a
  `Tenant.address` attribute that has never existed on that model,
  crashing every rental receipt print. Fixed (unrelated to Phase 2.0,
  found earlier in this session).

## Testing
Backend tests were added for every change above (`tests/test_properties.py`,
`tests/test_units.py`, `tests/test_reports.py`). **These have not been
executed** — they were written and statically reviewed only, since the
sandbox this was built in has no network access to install
FastAPI/SQLAlchemy/pytest or the frontend's npm dependencies.

**Before deploying:**
```bash
docker compose up -d          # or your usual local stack
docker compose exec backend alembic upgrade head
docker compose exec backend pytest
cd frontend && npm install && npx tsc --noEmit && npm run build
```
