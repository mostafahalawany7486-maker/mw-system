# Phase 7 — Rental Contracts (Company → Tenant): Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Rental Contract
| Field | Rule |
|---|---|
| `tenant_id` | Required, must reference an existing, non-deleted tenant (400 if invalid). **A blacklisted tenant is allowed** — this is a business decision left to staff, not a hard system block. The activity log records a warning, and the API/UI both surface `tenant_is_blacklisted` prominently |
| `property_id` | Required, must reference an existing, non-deleted property (400 if invalid). No type restriction — any property (building, unit, land, etc.) can be the subject of a rental contract |
| `start_date` / `end_date` | Both required; `end_date` must be strictly after `start_date` (422 otherwise) |
| `rent_amount` | Required, must be ≥ 0 |
| `security_deposit_amount` | Optional, defaults to 0, must be ≥ 0 |
| `payment_frequency` | One of `monthly`, `quarterly`, `semi_annual`, `annual`, `one_time`, `custom` |
| `contract_number` | System-generated (`RNT-000001` sequence), never client-supplied, immutable |
| Editing | Blocked (409) once a contract is `terminated` or `renewed` — same rule as Lease Agreements (Phase 3) |

## Discounts
| Rule |
|---|
| `discount_type` is one of `none`, `percentage`, `fixed` |
| If `percentage`: `discount_value` must be between 0 and 100 (422 otherwise) |
| If `fixed`: `discount_value` is any non-negative amount, no upper bound enforced against `rent_amount` (a discount larger than the rent is allowed but would produce an unusual — though not rejected — total; this is treated as a business judgment call, not a system error) |
| The discount is computed once at schedule-generation time and stored on each installment (`discount_amount`) — later changes to the contract's `discount_value` do not retroactively alter already-generated installments |

## Taxes
| Rule |
|---|
| `tax_rate` must be between 0 and 100 (422 otherwise) |
| Tax is computed on the **post-discount** amount: `(rent_amount - discount_amount) * tax_rate / 100` |
| Like discounts, tax is computed once at generation time and stored per installment (`tax_amount`) — not recalculated dynamically |

## Late Fees
| Rule |
|---|
| `late_fee_type` is one of `percentage`, `fixed` |
| `late_fee_grace_period_days` defaults to 5 — an installment must be overdue by *more* than this many days before a fee is assessed (a payment 1 day late within a 5-day grace period is not penalized) |
| The maintenance sweep is idempotent: a late fee is only assessed once per installment (checks `late_fee_amount == 0` before assessing) — running the sweep repeatedly never stacks fees |
| Late fees remain even if the installment is later marked paid, preserving the historical record of what was actually owed |

## Payment Schedule
| Rule |
|---|
| `payment_frequency=custom` cannot use auto-generation (400) — installments must be added manually one at a time |
| Auto-generating a schedule when one already exists requires `overwrite_existing=true` (409 otherwise) — prevents accidental duplicate schedules |
| Every installment stores its own `discount_amount`, `tax_amount`, and `late_fee_amount` independently, so `total_payable` is always accurate per installment even as contract-level settings change over time |

## Status Machine & Property Sync
| Transition | Side effect |
|---|---|
| `draft → active` (Activate) | Property's `availability_status` is set to `leased` |
| `active → terminated` (Terminate, requires date + reason) | Property's `availability_status` is set back to `available` |
| `active → renewed` (Renew) | Creates a new contract row; property stays `leased` throughout (no gap in occupancy) |
| Maintenance sweep | Auto-expires any `active` contract whose `end_date` has passed (does not touch property availability — an expired contract without a renewal or termination is flagged for staff attention, not auto-freed) |

## Cross-cutting
- Contract History and Attachments both reuse the exact generic systems from Phase 1 (`ActivityLog`/`Attachment` with `entity_type="rental_contract"`) — no new tables, no new code paths.
