# Phase 2 — Property Owners: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phase 1 must be running (`docker compose up`) with migrations
applied through `0002_property_owners`. Run `python seed.py` to load sample
owners (OWN-000001 Robert Chen, OWN-000002 Skyline Holdings LLC).

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0002_property_owners` without error
- [ ] Tables `owners`, `owner_addresses`, `owner_bank_accounts`, `owner_contacts`, `owner_documents` exist with all mandatory audit columns (id, uuid, status, created_at, updated_at, deleted_at, created_by, updated_by)
- [ ] `python seed.py` creates the `owners` permission module (view/create/edit/delete) and assigns it to Administrator (all), Branch Manager (view/create/edit), Staff (view)
- [ ] Seed creates 2 sample owners with addresses, a bank account, and a contact already attached

## 2. Owner Creation — Individual
- [ ] Create an individual owner with first name + last name only → succeeds, `owner_code` auto-generated (e.g. `OWN-000003`)
- [ ] Create an individual owner missing `last_name` → 422 validation error naming the missing field
- [ ] Create an individual owner with a `national_id` that's already used by another owner → 409 conflict
- [ ] `display_name` on the created owner equals `"{first_name} {last_name}"`

## 3. Owner Creation — Company
- [ ] Create a company owner with `company_name` only → succeeds
- [ ] Create a company owner missing `company_name` → 422 validation error
- [ ] `display_name` on a company owner equals the `company_name`

## 4. Owner Type Validation
- [ ] `owner_type` outside `individual`/`company` (e.g. `"nonprofit"`) → 422
- [ ] Switching an owner's type after creation is NOT exposed via the update endpoint (only type-appropriate fields are editable) — confirm `OwnerUpdate` has no `owner_type` field

## 5. List, Search, Filters
- [ ] Owner list is paginated (10/page default), matches `total`/`total_pages`
- [ ] Search matches on: owner code, first/last name, company name, email, phone, national ID
- [ ] Filter by `owner_type=individual` returns only individuals; `owner_type=company` returns only companies
- [ ] Sorting works on `created_at`, `owner_code`, `company_name`, `last_name`

## 6. Owner Detail & Edit
- [ ] Owner detail page loads all sub-resources in a single request (addresses, bank accounts, contacts, documents counts)
- [ ] Editing common fields (email, phone, website) saves and reflects immediately
- [ ] Editing type-specific fields (national ID for individual; registration number for company) saves correctly
- [ ] A user without `owners.edit` sees the Edit button hidden; a direct API `PUT` attempt returns 403

## 7. Addresses
- [ ] Add multiple addresses of different types (mailing/permanent/property/other)
- [ ] Setting a new address as primary automatically un-sets the previous primary (only one `is_primary=true` at a time) — verify via `GET /owners/{id}` that exactly one address has `is_primary=true`
- [ ] Edit an address; delete an address (soft-delete, disappears from the list)

## 8. Bank Accounts
- [ ] Add a bank account with IBAN; add a second with only account number — both save correctly
- [ ] Only one bank account can be primary at a time (same rule as addresses)
- [ ] Dashboard's "Missing Bank Details" widget count decreases by 1 immediately after adding the first bank account to an owner that had none
- [ ] Delete a bank account; confirm it's removed from the list

## 9. Contacts
- [ ] Add multiple contacts to a company owner (e.g. finance contact + operations contact)
- [ ] Only one contact can be primary at a time
- [ ] Edit and delete contacts work correctly

## 10. Documents
- [ ] Upload a valid document (PDF/image) with type, number, and expiry date → succeeds, appears in list
- [ ] Upload a disallowed file type (e.g. `.exe`) → 400, clear error message
- [ ] Upload a file over the size limit → 400
- [ ] A document with `expiry_date` in the past shows an "Expired" badge in the UI (`is_expired: true` in the API response)
- [ ] Edit document metadata (number, expiry date) without re-uploading the file
- [ ] Delete a document removes both the DB record and the underlying file (same guarantee as Phase 1 Attachments)

## 11. Notes & Activity History (reused from Phase 1 infrastructure)
- [ ] Add a note on the Owner detail page's Notes tab; appears immediately
- [ ] Pin a note; it sorts to the top
- [ ] Every create/update/delete action on the owner (and its sub-resources) appears in the History tab with a human-readable description
- [ ] Bank account additions also produce an Audit Log entry (field-level), visible to `audit.view` holders in the Phase 1 Audit Log page

## 12. Owner Dashboard
- [ ] Dashboard widgets show correct counts: total owners, individuals, companies, active owners, owners missing bank details
- [ ] "Recently Added" reflects the 5 most recently created owners, newest first
- [ ] Main system Dashboard (Phase 1) now also shows a "Property Owners" widget with the same total count

## 13. Permissions
- [ ] Staff role (view-only on owners) can see the Owners list and detail pages but cannot see Add/Edit/Delete buttons
- [ ] Staff attempting `POST /owners` directly via API → 403
- [ ] Branch Manager can create and edit owners but not delete them (no `owners.delete` in seeded role) → verify delete button hidden and API returns 403

## 14. Data Integrity / Soft Delete
- [ ] Deleting an owner soft-deletes it (`deleted_at` set); it disappears from the default list and `GET /owners/{id}` returns 404
- [ ] Deleting an owner does NOT hard-delete its addresses/bank accounts/contacts/documents (cascade is DB-level `ON DELETE CASCADE` only for hard deletes, which the API never performs)

## 15. UI / Responsive
- [ ] All 7 detail tabs (Overview, Addresses, Bank Accounts, Contacts, Documents, Notes, History) render without errors
- [ ] Owner list and detail page are usable on a 375px mobile viewport
- [ ] Loading spinners show during data fetches; empty states show when a sub-resource list is empty

## 16. Automated tests
- [ ] `pytest backend/tests/test_owners.py` passes all cases (individual/company validation, CRUD, sub-resources, permissions, file upload validation)
