# Phase 5 — Unit Management: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–4 running with migrations through `0005`. Run
`python seed.py` to load sample floors and unit-management data.

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0005_unit_management` without error
- [ ] `floors` table exists with mandatory audit columns
- [ ] `properties` table gained 7 new nullable columns: `floor_id`, `unit_number`, `rent_price`, `electricity_meter_number`, `water_meter_number`, `parking_space_id`, `storage_space_id` (additive — existing Phase 4 properties are unaffected)
- [ ] `python seed.py` creates 3 floors (3, 4, 5) under PRP-000002 (Business Bay Tower)
- [ ] Seed creates PRP-000005 (Parking Spot 12) and PRP-000006 (Storage Unit 3), both linked to PRP-000003 (the office unit) via `parking_space_id`/`storage_space_id`
- [ ] PRP-000003 has `unit_number="301"`, `rent_price=15000.00`, both meter numbers set, and `floor_id` pointing to Floor 3

## 2. Floors
- [ ] Create a floor under a Building property → succeeds
- [ ] Create a floor under a non-Building property (e.g. a Villa) → 400
- [ ] List floors for a building returns them sorted by floor number, each with an accurate `unit_count`
- [ ] Edit a floor's name/description/planned unit count
- [ ] Delete a floor that has zero units assigned → succeeds
- [ ] Delete a floor that has one or more units assigned → 409 ("still has units assigned")
- [ ] Floors endpoints require authentication (401) and `properties.view`/`properties.edit` permissions as appropriate

## 3. Unit Numbers & Rent Price
- [ ] Create/edit a unit with `unit_number` (e.g. "4B") — saves and displays correctly, searchable
- [ ] Create/edit a unit with `rent_price` — saves with correct decimal precision
- [ ] Negative `rent_price` → 422
- [ ] `rent_price` is distinct from a lease's actual `rent_amount` (Phase 3) — verify both can differ on the same unit without conflict (e.g. asking price $3,500 but signed lease at $3,300)

## 4. Electricity & Water Meters
- [ ] Set `electricity_meter_number` and `water_meter_number` on a unit — both save and display independently
- [ ] Both fields are optional; a unit without meters set shows them as empty/blank, not an error

## 5. Floor Assignment
- [ ] Assign a unit to a valid `floor_id` → succeeds, `floor_label` shows the floor's name/number on the unit's detail page
- [ ] Assign a unit to an invalid/nonexistent `floor_id` → 400
- [ ] A floor's `unit_count` increases immediately after assigning a new unit to it

## 6. Parking & Storage Assignment
- [ ] Assign an existing `parking`-type property as a unit's `parking_space_id` → succeeds, `parking_space_code` shows on the unit
- [ ] Assign a non-`parking`-type property (e.g. a villa) as `parking_space_id` → 400 with a clear message
- [ ] Assign an existing `storage`-type property as a unit's `storage_space_id` → succeeds
- [ ] Assign a non-`storage`-type property as `storage_space_id` → 400
- [ ] A unit cannot reference itself as its own `parking_space_id` or `storage_space_id` → 400

## 7. Availability (reused from Phase 4)
- [ ] Availability status behaves identically to Phase 4 — no regressions from the new unit fields
- [ ] Filtering the Properties list by `property_type` continues to work for all 10 types after the schema additions

## 8. Images & Documents (reused from Phase 4)
- [ ] Upload images and documents on a unit exactly as in Phase 4 — no regressions
- [ ] Confirm the Phase 4 cover-photo and expiry-flag behavior still works unchanged

## 9. UI
- [ ] A Building's detail page shows both a "Units" tab and a new "Floors" tab
- [ ] Non-Building properties do NOT show a Floors tab
- [ ] The Overview tab's "Unit Details" section shows unit number, rent price, both meter numbers, assigned floor, and assigned parking/storage (or "—" when unset)
- [ ] The property creation form shows Unit Number and Rent Price fields for every type except Building

## 10. Permissions
- [ ] Staff (view-only) can view floors and unit-management fields but cannot create/edit/delete floors or reassign parking/storage — buttons hidden, API returns 403
- [ ] Branch Manager can manage floors and unit fields (create/edit) but cannot delete floors that still have units (409, not a permission issue)

## 11. Automated tests
- [ ] `pytest backend/tests/test_units.py` passes all cases (floor CRUD, building-only constraint, unit fields, parking/storage type validation, self-reference prevention)
