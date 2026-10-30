# Phase 9 — Maintenance: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–8 running with migrations through `0009`. Run
`python seed.py` to load 1 contractor, 2 technicians, and 3 sample
maintenance requests.

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0009_maintenance` without error
- [ ] Tables `contractors`, `technicians`, `maintenance_requests`, `maintenance_materials`, `maintenance_labor_costs`, `maintenance_photos` exist with all mandatory audit columns
- [ ] `python seed.py` registers the `maintenance` permission module — Administrator (all), Branch Manager (view/create/edit), Staff (view + create, so front-line staff can report issues even without broader edit rights)
- [ ] Seed creates CON-000001 (CoolBreeze HVAC Services) and TEC-000001 (in-house, no contractor) + TEC-000002 (contracted, belongs to CoolBreeze)
- [ ] Seed creates MNT-000001 (completed, plumbing, with 2 materials + 1 labor entry), MNT-000002 (in_progress, urgent HVAC, with 1 labor entry), MNT-000003 (reported, unassigned)
- [ ] No photos are seeded (documented limitation — seeding real image files isn't practical from a script; verify by uploading a photo manually in the UI instead)

## 2. Contractors
- [ ] Create a contractor — succeeds, `contractor_code` auto-generated (`CON-000002`)
- [ ] Invalid `specialty` (not in the allowed set) → 422
- [ ] Deleting a contractor with technicians still linked to them → 409 ("reassign or remove those technicians first")
- [ ] Deleting a contractor with no technicians → succeeds

## 3. Technicians
- [ ] Create a technician with no `contractor_id` → `is_in_house: true`
- [ ] Create a technician with a valid `contractor_id` → `is_in_house: false`, `contractor_name` populated
- [ ] Invalid `contractor_id` → 400
- [ ] Invalid `specialty` → 422

## 4. Maintenance Requests — Creation & Priority
- [ ] Create a request with a valid `property_id` → succeeds as `reported`, `request_number` auto-generated (`MNT-000004`)
- [ ] Invalid `property_id` → 400
- [ ] Invalid `tenant_id` (if supplied) → 400
- [ ] Invalid `priority` (not low/medium/high/urgent) → 422
- [ ] Invalid `category` (not in the allowed set) → 422
- [ ] `scheduled_date` before `reported_date` → 422
- [ ] A request can be created without a `tenant_id` (staff-reported, e.g. a routine inspection finding)

## 5. Contractors & Technicians on a Request
- [ ] Assign a contractor and/or technician to a `reported` request → status becomes `assigned`
- [ ] Assigning with neither a contractor nor a technician → 422
- [ ] Assigning an invalid `assigned_contractor_id`/`assigned_technician_id` → 400
- [ ] Reassigning an already-`assigned`/`in_progress`/`on_hold` request → succeeds, stays in its current status (reassignment doesn't reset progress)

## 6. Materials
- [ ] Add a material line item → `total_cost = quantity × unit_cost` computed correctly
- [ ] Negative `quantity` or `unit_cost` → 422
- [ ] Deleting a material recalculates the request's `total_material_cost` on next fetch

## 7. Labor Cost
- [ ] Add a labor entry with a technician → `total_cost = hours × hourly_rate`, `technician_name` populated
- [ ] Add a labor entry with just a contractor (no specific technician) — also valid
- [ ] Negative `hours` or `hourly_rate` → 422
- [ ] Deleting a labor entry recalculates `total_labor_cost` on next fetch
- [ ] `total_actual_cost` on the request always equals `total_material_cost + total_labor_cost` — never a manually entered number

## 8. Before / After Photos
- [ ] Upload a photo with `photo_type=before` → succeeds, appears under "Before"
- [ ] Upload a photo with `photo_type=after` → succeeds, appears under "After"
- [ ] Invalid `photo_type` (anything other than before/after) → 400
- [ ] Disallowed file extension → 400 (reuses the same `ALLOWED_UPLOAD_EXTENSIONS` validation as Phase 1 attachments)
- [ ] Delete a photo → removed from the list

## 9. Status Machine
- [ ] Full lifecycle: `reported → assigned → in_progress → on_hold → in_progress → completed` all succeed in sequence
- [ ] `reported → in_progress` directly (skipping assign) → 409
- [ ] Any transition attempted from `completed` or `cancelled` (terminal states) → 409
- [ ] `cancel` is reachable from every non-terminal state, with a required reason
- [ ] `hold` requires a reason; `cancel` requires a reason; `complete` requires a completion date
- [ ] Cannot edit title/description/priority/etc. on a `completed` or `cancelled` request (409)

## 10. History
- [ ] History tab shows every action in plain English: created, assigned, started, on_hold, resumed, completed, cancelled, material_added, labor_cost_added, photo_added

## 11. Dashboard
- [ ] Widgets show correct counts: total, by status (reported/assigned/in_progress/on_hold/completed/cancelled), overdue (open requests past their `scheduled_date`), urgent-and-open, and total actual cost of requests completed this month
- [ ] Main Phase 1 Dashboard also shows an "Open Maintenance Requests" widget matching the sum of non-terminal statuses

## 12. Permissions
- [ ] Staff (view + create only) can report new issues but sees no assign/start/hold/complete/cancel/delete controls on existing ones
- [ ] Branch Manager can manage requests fully (create/edit/assign/status transitions, since these all reuse `maintenance.edit`) but cannot delete (no `maintenance.delete` in seeded role)

## 13. Automated tests
- [ ] `pytest backend/tests/test_maintenance.py` passes all cases (contractors, technicians, request validation, full status lifecycle, invalid transitions, materials/labor cost computation, photo upload incl. invalid type, dashboard, history, permissions)
