# Phase 3 — Lease Agreements: Validation Rules

Adds to (does not replace) `docs/validation-rules.md` and `docs/phase2-validation-rules.md`.

## Lease Agreement
| Field | Rule |
|---|---|
| `owner_id` | Required, must reference an existing, non-deleted owner (400 if invalid) |
| `property_reference` | Required free text (no formal Property entity yet — see model docstring in `app/models/lease.py`) |
| `start_date` / `end_date` | Both required; `end_date` must be strictly after `start_date` (422) |
| `payment_frequency` | Required, one of `monthly`, `quarterly`, `semi_annual`, `annual`, `one_time`, `custom` |
| `rent_amount` | Required, must be ≥ 0 |
| `security_deposit_amount` | Optional, defaults to 0, must be ≥ 0 |
| `security_deposit_status` | One of `held`, `returned`, `partially_returned`, `forfeited` |
| `contract_number` | System-generated (`LSE-000001` sequence), never client-supplied, immutable |
| `contract_status` | Never directly settable via `PUT` — only changes through the dedicated `/activate`, `/terminate`, `/renew` endpoints, each enforcing its own precondition (see status machine below) |

## Status Machine (enforced server-side, not just hidden in the UI)
```
draft --activate--> active --terminate--> terminated
                       |
                       +--renew--> (new lease created, old one -> renewed)
                       |
              (end_date passes, via maintenance sweep) --> expired
```
- Only `draft` leases can be activated (409 otherwise).
- Only `active` leases can be terminated or renewed (409 otherwise).
- `terminated` and `renewed` leases are permanently read-only via `PUT /leases/{id}` (409) — their history is preserved as an immutable record.
- Renewing a lease with `is_renewable=false` is rejected (409).

## Payment Installment
| Field | Rule |
|---|---|
| `due_date`, `amount` | Required on manual add |
| `status` | One of `pending`, `paid`, `overdue`, `cancelled` |
| Auto-generation | Rejected (400) if the lease's `payment_frequency` is `custom` — those schedules must be built manually, since there's no fixed interval to compute from |
| Auto-generation | Rejected (409) if installments already exist, unless `overwrite_existing=true` is passed |

## Renewal Reminders
- `renewal_notice_days` (per-lease, default 30) defines the window before `end_date` in which a lease is considered "expiring soon."
- `renewal_reminder_sent` prevents duplicate notifications across repeated maintenance sweeps for the same lease.
- See `docs/phase3-renewal-reminders.md` for the current on-demand trigger and how to automate it in production.
