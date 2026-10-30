# Cascading Property Selector (Owner → Property → Floor → Apartment)

## What was there before (analysis, done first, before any change)

- **RentalContract creation** (`RentalFormModal.tsx`): a single flat
  `<select>` of up to 100 properties system-wide — no owner filter, no
  floor grouping, and no visibility into whether a unit already had an
  active tenant. `property_id` was already a real FK sent to the
  backend, so this half of the request was a UX/filtering gap, not a
  data-modeling one.
- **LeaseAgreement creation** (`LeaseFormModal.tsx`): a genuinely manual
  **free-text** `property_reference` field (`type="text"`, no relation
  to any `Property` row at all) — even though `LeaseAgreement.property_id`
  has existed as a real, nullable FK since Phase 3's own migration. The
  form simply never used it. `property_reference` itself stays on the
  model and stays required by `LeaseAgreementCreate` (other code — the
  printed lease documents — reads it as free text), so it wasn't
  removed; it's now auto-filled from the structured selection instead
  of hand-typed, and still editable if a different wording is needed.
- The underlying data model already fully supported the requested
  hierarchy: `Property.parent_property_id` (Building → Unit),
  `Property.floor_id` → `Floor` (Phase 5), and the Occupancy Engine
  (Phase 18) already computed live per-unit occupancy + active tenant.
  **No new table, column, or relationship was needed** — this is a
  selection-UI feature over data that already existed.

## What was added

**One necessary, minimal, additive backend change** (everything else is
frontend composition over existing endpoints):
- `PropertyListItemOut.parent_property_id` — was already on
  `PropertyDetailOut` but missing from the *list* serializer, so a
  cascading selector had no way to tell a Building apart from a Unit
  from the list endpoint alone. Adding it required zero service-layer
  changes (Pydantic reads it straight off the same ORM object already
  being returned).
- `GET /properties?top_level_only=true` — a new opt-in filter
  (`Property.parent_property_id.is_(None)`), alongside the existing
  `parent_property_id=<id>` filter (which asks for children of *one*
  specific parent — a different question). Off by default; every
  existing caller of this endpoint is unaffected.

**New frontend component**, `PropertyHierarchySelector.tsx`, composed
entirely from existing, already-working endpoints:
`GET /owners`, `GET /properties?owner_id=&top_level_only=true`,
`GET /properties/{id}/floors` (Phase 5), `GET /properties?parent_property_id=&floor_id=`
(already-supported filters), and `GET /occupancy/units?building_id=`
(Phase 18) for the occupied/vacant cross-reference.

## How invalid selections are prevented

- Each level's `<select>` is disabled/hidden until its parent is
  chosen — Floor doesn't render until a Property with floors is picked;
  Apartment doesn't render until a Floor is picked (or immediately, if
  the property has units but no floor records at all).
- Three shapes are handled automatically, not configured per case:
  1. **Property has no child units** (villa, standalone unit) → it
     finalizes as the selected unit immediately, no further steps.
  2. **Property has units but no Floor records** → skips straight to a
     flat Apartment/Unit dropdown.
  3. **Property has units grouped under floors** → full 4-level cascade.
     Units with `floor_id = NULL` are still reachable via a synthetic
     "Unassigned units" floor entry — never silently dropped from the
     list.
- **Occupied-unit detection**: once a unit is picked, its live
  occupancy (from the Occupancy Engine) is shown — vacant (green) or
  occupied/notice-period/etc. (red, with the current tenant's name and
  contract end date). This is advisory, matching exactly where the
  backend actually enforces the rule: **creating** a second draft
  contract for an occupied unit is allowed (harmless — it's not
  active), but **activating** it is blocked by the existing Phase 18
  "one active lease per unit" check in `RentalService.activate_contract()`.
  Nothing about that enforcement was changed. If the signed-in user
  lacks `occupancy.view`, the badge is silently omitted rather than
  blocking the form — read-only convenience, not a hard dependency.

## Self-audit (developer + auditor pass)

- **Duplicate data / conflicting relationships**: none created — no new
  table, no new FK, no new enum. The two schema/filter additions are
  pure additions to existing, already-returned data.
- **Broken links**: grepped both rewritten forms for leftover references
  to the state variables they replaced (`properties` in
  `RentalFormModal.tsx`, `owners` in `LeaseFormModal.tsx`) — none found.
- **Backward compatibility**: `GET /properties` with no new params
  behaves identically to before (both additions are opt-in/default-off).
  `LeaseAgreementCreate.property_reference` stays required and
  unchanged in meaning; `property_id` was already optional.
- **Scalability**: property/floor/unit fetches are capped
  (`page_size=200`) and scoped by owner/building at each step rather
  than ever loading the whole portfolio at once, which is the actual
  fix for the original flat 100-item dropdown not scaling.
- **Not tested by running the app** — this environment has no network
  access to install dependencies or start the servers. Every file was
  syntax-checked (`ast.parse` for Python, brace/paren/bracket balance
  for TypeScript) and every field name/endpoint/permission was verified
  against the actual source it calls, not from memory — but that is not
  a substitute for exercising the real flows end to end. Please run
  through: create a Rental Contract for a vacant unit, for an occupied
  unit (confirm the warning shows and activation is still blocked by
  the backend), and a Lease Agreement for a villa with no child units
  (confirms the "no floors/units" direct-selection path), before
  relying on this in production.
