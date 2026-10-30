# Phase 4 — Property Management: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–3 running with migrations through `0004`. Run
`python seed.py` to load the amenities catalog and 4 sample properties.

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0004_property_management` without error
- [ ] Tables `properties`, `amenities`, `property_amenities`, `property_images`, `property_documents` exist with all mandatory audit columns
- [ ] `lease_agreements` gained a nullable `property_id` column (additive — existing Phase 3 leases are unaffected)
- [ ] `python seed.py` registers the `properties` permission module and assigns it to Administrator (all), Branch Manager (view/create/edit), Staff (view)
- [ ] Seed creates a 12-item amenities catalog and 4 sample properties (PRP-000001 Villa, PRP-000002 Building, PRP-000003 Office unit inside the building, PRP-000004 Warehouse)
- [ ] PRP-000001 is linked as the current property on LSE-000001 (active lease); PRP-000002 is linked on LSE-000002 (draft lease)

## 2. Property Creation — All 10 Types
- [ ] Create a property of each type: Building, Villa, Apartment, Commercial Unit, Warehouse, Shop, Office, Land, Parking, Storage — all succeed
- [ ] An invalid `property_type` (e.g. `"mansion"`) → 422
- [ ] `property_code` is auto-generated (`PRP-000005`, etc.), never client-settable
- [ ] Creating with an invalid `owner_id` → 400
- [ ] Creating with an invalid `parent_property_id` → 400

## 3. Property Code & Internal Code
- [ ] `property_code` is unique and sequential
- [ ] `internal_code` is optional free text, editable, and searchable

## 4. Owner & Lease Contract Linkage
- [ ] `owner_id` is required and shown as `owner_display_name` on both list and detail views
- [ ] A property with no active lease shows `current_lease_id: null` on its detail view
- [ ] Activating a lease that references this property (`property_id` set on the lease) makes it appear as the property's "Current Lease Contract" immediately
- [ ] Terminating or letting that lease expire removes it from "current lease" (only `active` leases count)

## 5. Location & GPS
- [ ] Address fields (line 1/2, city, country, postal code) save and display correctly
- [ ] Latitude outside [-90, 90] → 422
- [ ] Longitude outside [-180, 180] → 422
- [ ] Valid GPS coordinates save with 6 decimal places of precision

## 6. Images
- [ ] Upload a valid image (PNG/JPG) → succeeds, appears in the gallery
- [ ] Upload a non-image file (e.g. PDF) to the Images endpoint → 400 with a clear message ("use Documents for other file types")
- [ ] Marking an image as cover automatically un-marks any previous cover photo (only one `is_cover=true` at a time)
- [ ] Delete an image → removed from gallery and underlying file deleted

## 7. Documents
- [ ] Upload a document (title deed, floor plan, permit, inspection report, other) with number and expiry date
- [ ] A document with a past `expiry_date` shows `is_expired: true` and an "Expired" badge in the UI
- [ ] Edit document metadata without re-uploading the file
- [ ] Delete a document → removed and underlying file deleted
- [ ] Same file-type/size limits as Phase 1/2/3 apply (`ALLOWED_UPLOAD_EXTENSIONS`, `MAX_UPLOAD_SIZE_MB`)

## 8. Amenities
- [ ] Amenities catalog lists 12 seeded items grouped by category
- [ ] Assign multiple amenities to a property at creation time via `amenity_ids`
- [ ] Update a property's amenity list via `PUT` with a new `amenity_ids` array — fully replaces the previous set
- [ ] Add a brand-new amenity to the catalog inline from the property detail page
- [ ] Duplicate amenity name → 409

## 9. Availability & Status
- [ ] `availability_status` accepts only `available`, `leased`, `reserved`, `under_maintenance`, `off_market` — anything else → 422
- [ ] Changing availability status is reflected immediately in the list view's badge and the dashboard's by-availability counts
- [ ] The generic `status` field (active/inactive/archived, from BaseModel) is distinct from `availability_status` and behaves like every other Phase 1–3 entity (soft-delete sets it to `archived`)

## 10. Building → Units Hierarchy
- [ ] Create a Building, then create an Apartment/Office/Shop with `parent_property_id` set to that building's ID
- [ ] The building's detail page shows a "Units" tab listing all its children
- [ ] Non-building property types do NOT show a Units tab
- [ ] `GET /properties/{building_id}/units` returns only that building's direct children

## 11. Search & Filters
- [ ] Search matches property code, internal code, title, address, and owner name
- [ ] Filter by `property_type`, `availability_status`, `owner_id`, `branch_id`, `city_id` all work independently and combined

## 12. Attachments Note
- [ ] Confirm Images and Documents are genuinely separate systems (an image uploaded via the Images tab does NOT appear in Documents and vice versa) — this is intentional per the model design, not a bug

## 13. Dashboard
- [ ] Widgets show correct total, by-type breakdown (all 10 types), and by-availability breakdown
- [ ] "Recently added" shows the 5 most recent properties
- [ ] Main Phase 1 Dashboard also shows a "Properties" widget matching the total count

## 14. Permissions
- [ ] Staff (view-only) can browse properties and their images/documents/amenities but sees no Add/Edit/Delete/Upload controls
- [ ] Staff attempting `POST /properties` or `POST /properties/{id}/images` directly via API → 403
- [ ] Branch Manager can create/edit properties and their sub-resources but not delete (no `properties.delete` in seeded role)

## 15. Automated tests
- [ ] `pytest backend/tests/test_properties.py` passes all cases (all 10 types, GPS bounds, hierarchy, amenities, images, documents, current-lease linkage, permissions)
