# Phase 6 — Tenant Management: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–5 running with migrations through `0006`. Run
`python seed.py` to load 3 sample tenants (2 in good standing, 1 blacklisted).

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0006_tenant_management` without error
- [ ] Tables `tenants`, `tenant_contacts`, `tenant_emergency_contacts`, `tenant_documents`, `tenant_ratings` exist with all mandatory audit columns
- [ ] `python seed.py` registers the `tenants` permission module and assigns it to Administrator (all), Branch Manager (view/create/edit), Staff (view)
- [ ] Seed creates TNT-000001 (Laura Martinez, individual, with an emergency contact), TNT-000002 (Northwind Logistics FZE, company, with a contact), and TNT-000003 (Derek Voss, blacklisted)

## 2. Tenant Creation — Individual
- [ ] Create an individual tenant with first + last name only → succeeds, `tenant_code` auto-generated (`TNT-000004`)
- [ ] Missing `last_name` → 422
- [ ] `national_id` already used by another tenant → 409
- [ ] `display_name` equals `"{first_name} {last_name}"`

## 3. Tenant Creation — Company
- [ ] Create a company tenant with `company_name` only → succeeds
- [ ] Missing `company_name` → 422
- [ ] `display_name` equals the `company_name`

## 4. Identity Fields
- [ ] `national_id` and `passport_number` both save independently for individual tenants
- [ ] `commercial_registration_number` and `tax_number` both save independently for company tenants
- [ ] All four fields are searchable (see Search & Filters below)

## 5. Contacts
- [ ] Add multiple contacts to a company tenant (e.g. finance + operations)
- [ ] Only one contact can be primary at a time — setting a new primary un-sets the previous one
- [ ] Edit and delete contacts work correctly

## 6. Emergency Contact
- [ ] Add an emergency contact with name, relationship, and phone (required) — email/address optional
- [ ] Missing `phone` → 422 (required field, unlike the general Contacts sub-resource)
- [ ] Multiple emergency contacts can be added; only one `is_primary=true` at a time
- [ ] Edit and delete emergency contacts work correctly

## 7. Documents
- [ ] Upload a National ID / Passport / Commercial Registration / Visa / Other document with number and expiry date
- [ ] A document with a past `expiry_date` shows `is_expired: true` and an "Expired" badge
- [ ] Disallowed file type (e.g. `.exe`) → 400
- [ ] Edit document metadata without re-uploading; delete removes both DB record and file

## 8. Attachments & Notes (reused infrastructure)
- [ ] Notes can be added and pinned on a tenant, same as every other Phase 1–5 entity
- [ ] History tab shows every create/update/blacklist/unblacklist/rating action in plain English

## 9. Blacklist
- [ ] Blacklist a tenant with a reason → `is_blacklisted: true`, reason/timestamp/actor recorded
- [ ] Blacklisting without a reason (empty string) → 422
- [ ] Blacklisting an already-blacklisted tenant → 409
- [ ] Unblacklist a tenant → `is_blacklisted: false`, reason/timestamp/actor all cleared
- [ ] Unblacklisting a tenant that isn't blacklisted → 409
- [ ] Blacklisted tenants show a clear red warning banner on their detail page and a badge in the list view
- [ ] Filtering the tenant list by `is_blacklisted=true` returns only blacklisted tenants

## 10. Tenant Rating
- [ ] Add a rating (1-5) with an optional comment → succeeds, appears in the Ratings tab
- [ ] Rating value outside 1-5 (e.g. 0 or 6) → 422
- [ ] Adding multiple ratings computes a correct running average (e.g. 5 and 3 → average 4.0)
- [ ] Delete a rating → average recalculates correctly afterward
- [ ] The tenant list and dashboard both show accurate average ratings

## 11. Search & Filters
- [ ] Search matches tenant code, first/last name, company name, email, phone, national ID, passport number, and commercial registration number
- [ ] Filter by `tenant_type=individual` / `company` works
- [ ] Filter by `is_blacklisted` works
- [ ] Filters can be combined with search

## 12. Dashboard
- [ ] Widgets show correct counts: total, individual/company breakdown, active, blacklisted, overall average rating
- [ ] "Recently added" reflects the 5 most recently created tenants
- [ ] Main Phase 1 Dashboard also shows a "Tenants" widget matching the total count

## 13. Permissions
- [ ] Staff (view-only) can browse tenants, contacts, documents, and ratings but sees no Add/Edit/Delete/Blacklist/Rate controls
- [ ] Staff attempting `POST /tenants` or `POST /tenants/{id}/blacklist` directly via API → 403
- [ ] Branch Manager can create/edit tenants (including blacklist/rate, since those use `tenants.edit`) but cannot delete (no `tenants.delete` in seeded role)

## 14. Automated tests
- [ ] `pytest backend/tests/test_tenants.py` passes all cases (individual/company validation, CRUD, blacklist, rating, sub-resources, permissions)
