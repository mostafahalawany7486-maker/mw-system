# Phase 3 — Lease Agreements: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1 & 2 running with migrations through `0003`. Run
`python seed.py` to load sample leases (LSE-000001 active, LSE-000002 draft).

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0003_lease_agreements` without error
- [ ] Tables `lease_agreements`, `lease_payment_installments` exist with all mandatory audit columns
- [ ] `python seed.py` registers the `leases` permission module and assigns view/create/edit to Branch Manager, view to Staff
- [ ] Seed creates LSE-000001 (active, linked to Robert Chen) and LSE-000002 (draft, linked to Skyline Holdings)

## 2. Lease Creation
- [ ] Create a lease against a valid owner → succeeds, `contract_number` auto-generated (`LSE-000003`), status starts as `draft`
- [ ] Create a lease with `end_date <= start_date` → 422
- [ ] Create a lease with an invalid `owner_id` → 400
- [ ] Create a lease with negative `rent_amount` or `security_deposit_amount` → 422
- [ ] Create a lease with an invalid `payment_frequency` (e.g. `"weekly"`) → 422
- [ ] `contract_number` is never client-settable — confirm it's absent from `LeaseAgreementCreate`

## 3. Contract Status Lifecycle
- [ ] New lease starts in `draft`
- [ ] Activating a `draft` lease → `active`; activating an already-`active` lease → 409
- [ ] Editing a lease is blocked (409) once it's `terminated` or `renewed`, but allowed while `draft` or `active`
- [ ] Terminating a `draft` lease → 409 (must be active first)
- [ ] Terminating an `active` lease with a reason → `terminated`, `terminated_date` and `termination_reason` recorded
- [ ] `run maintenance` (`POST /leases/maintenance/run`) auto-flips `active` leases past their `end_date` to `expired`

## 4. Renewal
- [ ] Renewing an `active`, renewable lease creates a NEW lease with a new `contract_number`, linked via `renewed_from_lease_id`
- [ ] The OLD lease's status flips to `renewed` (not deleted — its history and payment schedule remain intact)
- [ ] New lease's `start_date` defaults to old lease's `end_date + 1 day` when not explicitly provided
- [ ] Renewing a `draft` lease → 409
- [ ] Renewing a lease with `is_renewable=false` → 409
- [ ] Rent amount can be adjusted at renewal time (optional field) — confirm the new lease reflects the adjusted amount, old lease is untouched

## 5. Payment Schedule
- [ ] Auto-generate a `monthly` schedule for a 6-month lease → exactly 6 installments, one per month, each dated on `start_date` + N months
- [ ] Auto-generate for `quarterly`/`semi_annual`/`annual` → correct interval spacing
- [ ] Auto-generate for `one_time` → exactly 1 installment for the full rent amount on `start_date`
- [ ] Auto-generate for `custom` frequency → 400 (must add installments manually)
- [ ] Re-generating without `overwrite_existing=true` when installments already exist → 409
- [ ] Re-generating with `overwrite_existing=true` → old installments soft-deleted, new ones created
- [ ] Manually add an installment → appears in the schedule with the next sequential `installment_number`
- [ ] Mark an installment `paid` → sets `paid_date`, appears in Activity History
- [ ] Delete an installment → soft-deleted, removed from the list
- [ ] `run maintenance` flips `pending` installments whose `due_date` has passed to `overdue`

## 6. Security Deposit
- [ ] `security_deposit_amount` and `security_deposit_status` (`held`/`returned`/`partially_returned`/`forfeited`) are editable via `PUT /leases/{id}` while the lease is editable
- [ ] Setting an invalid `security_deposit_status` value → 422

## 7. Renewal Reminders
- [ ] A lease within its `renewal_notice_days` window (and `active`) shows `is_expiring_soon: true` and a positive `days_until_expiry`
- [ ] `run maintenance` sends an in-app notification to all active superusers for each newly-expiring lease, and sets `renewal_reminder_sent: true` so it's not re-sent on the next run
- [ ] The Leases dashboard's "upcoming renewals" list and the "Leases needing renewal attention" banner both reflect this correctly
- [ ] **Known limitation:** there is no background scheduler in Phase 1–3 (no Celery/cron yet). Reminders only fire when `POST /leases/maintenance/run` is called — see `docs/phase3-renewal-reminders.md` for how to wire this to a real scheduler in production.

## 8. Dashboard
- [ ] Widgets show correct counts: total/active/draft/terminated leases, expiring-soon count, total outstanding payment amount (sum of pending + overdue installments)
- [ ] Main Phase 1 Dashboard also shows an "Active Leases" widget matching this count

## 9. Attachments, Notes, History (reused infrastructure)
- [ ] Upload a document (e.g. signed PDF contract) on the Attachments tab; appears immediately, respects the same file-type/size limits as Phase 1/2
- [ ] Add and pin notes on the lease
- [ ] Every status transition (create/activate/terminate/renew), installment change, and edit appears in the History tab with a human-readable description

## 10. Search, Filters, Permissions
- [ ] Search matches contract number, property reference, and owner name
- [ ] Filter by `contract_status` and `owner_id` both work
- [ ] Staff (view-only) can see leases but not create/edit/delete/activate/terminate/renew — buttons hidden, API returns 403
- [ ] Branch Manager can create/edit/activate/terminate/renew but not delete (no `leases.delete` in seeded role)

## 11. Automated tests
- [ ] `pytest backend/tests/test_leases.py` passes all cases (validation, status transitions, renewal, payment schedule generation, permissions)
