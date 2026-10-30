# Phase 7 — Rental Contracts (Company → Tenant): Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–6 running with migrations through `0007`. Run
`python seed.py` to load 2 sample rental contracts.

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0007_rental_contracts` without error
- [ ] Tables `rental_contracts` and `rental_payment_installments` exist with all mandatory audit columns
- [ ] `python seed.py` registers the `rentals` permission module and assigns it to Administrator (all), Branch Manager (view/create/edit), Staff (view)
- [ ] Seed creates RNT-000001 (active, Laura Martinez subleasing the Sunset Villa, with a fixed discount and fixed late fee) and RNT-000002 (draft, Northwind Logistics subleasing the warehouse, with a tax rate and percentage late fee)
- [ ] PRP-000001 (the villa)'s `availability_status` is `leased` as a result of RNT-000001 being active

## 2. Rental Contract Creation
- [ ] Create a contract with a valid tenant + property → succeeds as `draft`, `contract_number` auto-generated (`RNT-000003`)
- [ ] `end_date` on or before `start_date` → 422
- [ ] Invalid `tenant_id` → 400
- [ ] Invalid `property_id` → 400
- [ ] Creating a contract for a **blacklisted** tenant is **allowed**, not blocked — the response includes `tenant_is_blacklisted: true`, and the activity log records a warning

## 3. Contract Number, Tenant, Property/Unit
- [ ] `contract_number` is unique, sequential, never client-settable
- [ ] `tenant_id` and `property_id` are both required and shown as `tenant_display_name`/`property_title` on list and detail views
- [ ] A property that is itself a unit within a building (per Phase 4/5) works identically to a standalone property — no separate "unit" field needed

## 4. Rent Amount & Deposit
- [ ] `rent_amount` is required, must be ≥ 0
- [ ] `security_deposit_amount` defaults to 0, accepts any non-negative value
- [ ] `security_deposit_status` (held/returned/partially_returned/forfeited) updates independently of contract status

## 5. Discounts
- [ ] `discount_type=none` → no discount applied to generated installments
- [ ] `discount_type=fixed` with a value → that exact amount is subtracted from every generated installment
- [ ] `discount_type=percentage` with a value between 0–100 → correct percentage of `rent_amount` is computed and applied
- [ ] `discount_type=percentage` with a value over 100 → 422

## 6. Taxes
- [ ] `tax_rate` (0–100) computes correctly on the **post-discount** rent amount for every generated installment
- [ ] `tax_rate` over 100 or negative → 422
- [ ] Changing `tax_rate` after installments are already generated does NOT retroactively change existing installments (only affects future schedule generation) — installments store their own `tax_amount` at generation time

## 7. Late Fees
- [ ] An installment past `due_date` gets marked `overdue` by the maintenance sweep
- [ ] Once also past the contract's `late_fee_grace_period_days`, a late fee is assessed (`fixed` = exact value; `percentage` = % of the installment's `amount`)
- [ ] Running the maintenance sweep twice does NOT stack/double the late fee on the same installment
- [ ] `total_payable` on each installment correctly reflects `amount - discount_amount + tax_amount + late_fee_amount`

## 8. Payment Schedule / Installments
- [ ] Auto-generate a schedule from `payment_frequency` (monthly/quarterly/semi_annual/annual/one_time) → correct number of installments at correct intervals
- [ ] `payment_frequency=custom` blocks auto-generation (400) — requires manually adding installments
- [ ] Regenerating without `overwrite_existing=true` → 409; with it, old installments are soft-deleted and replaced
- [ ] Manually add, edit, and delete individual installments
- [ ] Mark an installment `paid` → `paid_date`/`payment_method`/`reference_number` save correctly, activity log records it

## 9. Renewal
- [ ] Renew an active, renewable contract → creates a **new** contract row with a new `contract_number`, linked via `renewed_from_contract_id`; the old contract flips to `renewed`
- [ ] All discount/tax/late-fee settings carry over to the renewed contract by default
- [ ] Renewing a non-renewable contract (`is_renewable=false`) → 409
- [ ] Renewing a draft or already-terminated contract → 409

## 10. Status Machine
- [ ] `draft → active` via Activate — also flips the property's `availability_status` to `leased`
- [ ] `active → terminated` via Terminate (requires date + reason) — also flips the property's `availability_status` back to `available`
- [ ] Cannot edit a `terminated` or `renewed` contract's core terms (409)
- [ ] Maintenance sweep auto-expires active contracts whose `end_date` has passed

## 11. Contract History
- [ ] History tab shows every action in plain English: created, updated, activated, terminated, renewed, schedule generated, installment paid, late fee assessments (via the sweep)

## 12. Attachments
- [ ] Upload/list/delete attachments (signed contract PDF, addenda) using the same generic Phase 1 attachments system, scoped to `entity_type=rental_contract`

## 13. Dashboard
- [ ] Widgets show correct counts: total, active, draft, expiring soon, terminated, and total outstanding payment amount across all pending/overdue installments
- [ ] "Upcoming renewals" lists contracts within their `renewal_notice_days` window
- [ ] Main Phase 1 Dashboard also shows an "Active Rental Contracts" widget matching the count

## 14. Permissions
- [ ] Staff (view-only) can browse rental contracts and schedules but sees no Add/Edit/Delete/Activate/Terminate/Renew controls
- [ ] Branch Manager can manage contracts fully (create/edit/activate/terminate/renew, since all reuse `rentals.edit`) but cannot delete (no `rentals.delete` in seeded role)

## 15. Automated tests
- [ ] `pytest backend/tests/test_rentals.py` passes all cases (creation validation, blacklist warning, discount/tax computation, status transitions, renewal, payment schedule, maintenance sweep, permissions)
