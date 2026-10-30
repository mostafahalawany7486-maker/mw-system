# Phase 11 — Reports: Validation Rules & Design Notes

Adds to (does not replace) previous phases' validation-rules docs.

## Design Overview
Every report in this phase is computed live from Phases 1–10's existing
data — **no new persisted tables, no migration**. This is deliberately
distinct from Phase 10's accounting-grade financial statements (which
require posted journal entries): these are fast, operational business
reports computed directly from source transactional data (Financial
Transactions, Rental/Lease installments, Maintenance costs), useful even
if the GL isn't fully configured. A company using this system could rely
entirely on Phase 11's reports for day-to-day decisions without ever
touching Phase 10's formal ledger.

## Property Attribution
Several reports (Property, Income, Expense, Profit) need to know which
property a Financial Transaction relates to. The resolution order is:
1. `Transaction.property_id` if explicitly set
2. Otherwise, resolved via `Transaction.rental_contract_id → RentalContract.property_id`
3. Otherwise, the transaction is excluded from property-level breakdowns (it still counts in the report's overall totals)

## Vacancy & Occupancy: the "building" exclusion
`Property.property_type == "building"` rows are **excluded** from every
vacancy and occupancy calculation. Per the Phase 4/5 design, a Building
is a parent container for its units (via `parent_property_id`) — it is
not itself directly leasable space, so counting it as "vacant" or
"occupied" would double-count against its own units and misrepresent the
true vacancy picture. All other property types (villa, apartment,
warehouse, shop, office, etc.) are included.

## Occupancy Trend — a documented simplification
The occupancy trend is an **approximation**: for each of the trailing N
months, it computes `distinct properties with an active-at-the-time
rental contract ÷ current total leasable property count`. It does *not*
use a true historical snapshot of how many properties existed at that
time, because historical property counts aren't tracked anywhere in the
system. For a portfolio that hasn't grown or shrunk much recently, this
approximation is accurate; for a rapidly growing portfolio, older months
in the trend may understate true historical occupancy (since today's
larger property count is used as the denominator for past months too).
This is called out explicitly rather than presented as more precise than
it is.

## Expense vs. Maintenance Cost — avoiding double-counting
The Expense report shows `total_expense` (Financial `expense` and
`owner_payment` transactions) and `total_maintenance_cost` (Phase 9's
materials + labor cost, summed directly from `MaintenanceMaterial` and
`MaintenanceLaborCost`) as **two separate figures**, not summed together.
Whether a given maintenance job's cost has *also* been recorded as a
Financial `expense` transaction depends entirely on how staff invoiced
it — the system has no way to know if a maintenance cost and a financial
expense transaction refer to the same real-world payment. Summing them
by default would risk silently double-counting; showing them side by
side lets the person reviewing the report make that judgment call with
full information.

## Collection Rate
`collection_rate_percentage` (Financial report) is `paid_amount ÷
total_due_amount × 100` computed from Rental Payment Installments whose
`due_date` falls in the selected range — not from the installments'
`paid_date`. This means a payment made late (after the range) for an
installment due within the range still counts as "collected" for that
range, which is the standard way collection rate is measured (did we
eventually collect what was owed for this period), as opposed to a
cash-received-in-period metric (which the Financial report's
`total_income` figure already covers separately).

## Query Parameters
| Report | Parameters |
|---|---|
| Financial, Owner, Property, Income, Expense, Profit | `date_from`, `date_to` (both optional; default to "start of this month" through "today") |
| Tenant | `date_from`, `date_to` (optional; affects only "top tenants by payment" — counts and outstanding balances are always current) |
| Vacancy | none — always as-of-today |
| Occupancy | `months` (optional, 1–24, default 6) |
| Dashboard Analytics | none — always current month + trailing 6 months |

## Permissions
The `reports` permission module only meaningfully uses `.view` (every
endpoint is a read-only GET) — `.create`/`.edit`/`.delete` are generated
for schema consistency with every other module (same precedent as the
read-only `audit` module from Phase 1) but are never checked by any
endpoint. Both Branch Manager and Staff are granted `reports.view`,
consistent with their existing `financial.view` access from Phase 8 —
these reports are aggregate/summarized views, not raw ledger access.
