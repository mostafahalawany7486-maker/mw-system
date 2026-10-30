# Owner Ledger & Recoverable Expense Engine (Phase 17)

## Pre-implementation analysis

| Area | Finding |
|---|---|
| **Owner payouts** | `LeaseAgreement`/`LeasePaymentInstallment` (Phase 3) + `OwnerSettlementWorkflowService` (Phase 12) already pay owners for leasing their property to the company, via `FinancialService.create_transaction(OWNER_PAYMENT, ...)`. Untouched. Has no concept of a running owner balance or recoverable expenses. |
| **Payment & accounting transactions** | `Transaction`, `JournalEntry`, `PostingRule` (Phases 8/10) are the ledger of record. `JournalEntryService.auto_post_from_transaction` already degrades gracefully for a transaction type with no configured `PostingRule` (returns `None`, doesn't error) — confirmed safe to add new transaction types without touching that method. |
| **Existing PDF/reporting** | `AccountingReportService.property_cash_flow`/`property_balance_summary` (Phase 11, Property Profit Center) already exist — explicitly **not** extended or duplicated here, per the spec's own "Do not implement Profit Center or Analytics in this phase." |
| **User permissions/roles** | Extended the existing `module.action` catalog (`owner_ledger.view/create/edit`), same as every other module. |

## Two conflicts found, and the safest solution for each

### Conflict 1 — "never a company operating expense," but money still needs to hit the real ledger

The spec is explicit: *"This is NOT a normal company expense."* But "Accounting integration remains compatible" and "Trigger Accounting Event" mean the cash movement still needs a real `Transaction` → `JournalEntry`. The existing `TransactionType.EXPENSE` **is** a genuine company operating expense (it's what `MaintenanceWorkflowService.complete_and_settle`, Phase 12, posts for real maintenance costs) — reusing it for a recoverable expense would misclassify it exactly the way the spec forbids, and would be picked up by any existing/future company-expense report.

**Safest solution:** two new, purely additive `TransactionType` values — `RECOVERABLE_EXPENSE` and `OWNER_REIMBURSEMENT` (`app/models/financial.py`). This is the **one** existing file this phase needed to touch, and the change is minimal and safe:
- Nothing existing was renamed, removed, or had its meaning changed.
- Both new values were added to `INFLOW_TYPES`/`OUTFLOW_TYPES` so `create_transaction()`'s existing direction-detection logic (unchanged) handles them correctly.
- They were **not** added to `VALID_PAYMENT_METHODS`/`VALID_TRANSACTION_TYPES` in `app/schemas/financial.py` — so the raw `POST /financial/transactions` endpoint still rejects them. A recoverable expense or owner reimbursement can only be created through this new module's own dedicated endpoints, which is exactly what keeps it paired with an `OwnerLedgerEntry` every time (see `recoverable_expense_service.py`) — never created "loose."
- No `PostingRule` is pre-configured for either type (that's an administrative/seed-data decision, out of scope here); until one is, these transactions simply have no automatic GL entry yet, the same graceful degradation every other unmapped transaction type in this system already has.

### Conflict 2 — `owner_settlement_service.py` (the spec's file name) collides with an existing capability

The spec's file list for `business_workflows/owner_ledger/` includes `owner_settlement_service.py`. An `OwnerSettlementWorkflowService` **already exists** (Phase 12) and already pays out lease installments correctly. Two earlier phases each had to *retire* an older module when a newer one fully superseded it (see `app/business_workflows/__init__.py`'s docstring) — but this isn't that situation: the existing service doesn't know about the new ledger, and the new module doesn't need to reimplement lease payouts.

**Safest solution:** `owner_settlement_service.py` defines `OwnerLedgerSettlementService` (a distinct class name, avoiding the identity collision) that **delegates** to the existing `OwnerSettlementWorkflowService.settle_owner_installment()` unchanged, and adds exactly one new thing: mirroring the resulting payout into the Owner Ledger as an `OWNER_PAYMENT` debit entry, so it shows up on an Owner Statement. The old service is untouched and still fully usable on its own (it just won't appear in a statement unless called through this wrapper). No new API endpoint calls this in this phase — the spec's own requested API surface for Owner Ledger doesn't include a settlement endpoint — it's available for a future router/script to use.

## New database table

One new table, additive only — `owners`, `properties`, and `transactions` are **not modified**. See `app/models/owner_ledger.py`.

### `owner_ledger_entries`
Append-only: spec — *"No transaction can be deleted. Only reversal entries are allowed."* There is no update or delete path anywhere in this module for a posted entry's financial fields.

| Column | Notes |
|---|---|
| `id`…`updated_by` | Standard audit columns |
| `owner_id` | FK → `owners.id`, required |
| `property_id` | FK → `properties.id`, nullable (some entries, e.g. a general adjustment, aren't property-specific) |
| `transaction_date`, `transaction_type` | `transaction_type` is one of the 9 spec-listed values (`OwnerLedgerTransactionType`) |
| `expense_category` | Only meaningful for `recoverable_expense` — maintenance / municipality_fees / government_fees / electricity / water / emergency_repairs / insurance / other |
| `reference_type`, `reference_id` | Polymorphic pointer to whatever produced this entry (a `Transaction`, a lease installment, or `"manual"`) — not a foreign key, since the source table varies; same pattern `ActivityLog.entity_id` / `JournalEntry.source_transaction_id` already use elsewhere in this codebase |
| `description`, `debit`, `credit` | An entry is always single-sided — exactly one of `debit`/`credit` is non-zero, enforced by `OwnerLedgerValidator.validate_single_sided` |
| `balance` | The running balance **after** this entry — stored, not computed live. Safe precisely because the ledger is append-only (see the model's own docstring) |
| `entry_status` | `active` / `reversed` / `reversal` |
| `reversal_of_id`, `reversed_by_id` | Self-referential links between an original entry and the entry that reversed it |

`building_id`/`building_name`/`owner_name`/`property_title` are **read-only computed properties**, resolved through `property_id → Property.parent`/`owner_id → Owner`, exactly like every prior phase's models — never stored/duplicated columns.

**Balance convention:** a positive balance is the net amount the company currently owes the owner (a vendor/supplier-style sub-ledger). `RENTAL_INCOME`/`RECOVERED_AMOUNT`/`OPENING_BALANCE` are credits (increase it); `MANAGEMENT_FEE`/`MAINTENANCE_EXPENSE`/`RECOVERABLE_EXPENSE`/`OWNER_PAYMENT` are debits (decrease it — a `RECOVERABLE_EXPENSE` debit is exactly "increase owner outstanding balance" the spec asks for, just expressed as a debit in the sign convention above, i.e. the amount by which the owner now owes the company more). `ADJUSTMENT` has no fixed direction — the caller states debit or credit explicitly.

Migration: `app/alembic/versions/0021_owner_ledger_engine.py`.

## Business rules (per spec, implemented verbatim)

> "When company pays: Create Recoverable Expense, Increase Owner Outstanding Balance."
> "When owner reimburses company: Create Recovered Amount, Reduce Outstanding Balance."

Both implemented in `recoverable_expense_service.py`:
- `create_recoverable_expense()` → posts a `Transaction` (type `RECOVERABLE_EXPENSE`, never `EXPENSE`) + an `OwnerLedgerEntry` debit.
- `record_recovered_payment()` → posts a `Transaction` (type `OWNER_REIMBURSEMENT`) + an `OwnerLedgerEntry` credit.

`OwnerBalanceService.get_outstanding_recoverable_expenses()` computes the net not-yet-recovered amount (`Σ RECOVERABLE_EXPENSE debits − Σ RECOVERED_AMOUNT credits`) directly — distinct from the overall running balance, which also includes rental income/management fees/owner payments.

## Reversal, not deletion

`OwnerLedgerService.reverse_entry()` appends a **new** entry with debit/credit swapped, dated today (or a caller-supplied `reversal_date`) — it never mutates or deletes the original row's financial fields, only its `entry_status`/`reversed_by_id` linkage. This is the exact same design `JournalEntryService.reverse_entry` (Phase 10) already uses for `JournalEntry` — reused as a *pattern*, not code (different table, same proven idea). Reversing an already-reversed entry, or reversing a reversal entry itself, is rejected (`AlreadyReversedError` / `CannotReverseAReversalError`).

## Owner Statement

`OwnerStatementService.generate_statement(owner_id, date_from, date_to)` returns every spec-required line — Opening Balance, Rental Income, Management Fees, Recoverable Expenses, Recovered Amounts, Other Adjustments, Net Balance, Closing Balance — plus an extra **Owner Payments** line (a real owner statement needs it; the spec's list is a "must include," not a "must be limited to") and the full list of ledger entries in the period. `closing_balance` always equals the stored running `balance` on the last entry in range — a cheap, exact consistency check (exercised directly in tests).

## Owner Dashboard

`OwnerBalanceService.get_dashboard(owner_id)` — Current Balance, Outstanding Recoverable Expenses, Monthly Income, Monthly Expenses, Payments Made, Payments Received — all computed from the ledger, nothing stored separately to go stale.

## API

| Method & path | Permission | Notes |
|---|---|---|
| `POST /owner-ledger` | `owner_ledger.create` | Manual entry: `rental_income` / `management_fee` / `adjustment` / `opening_balance` |
| `GET /owner-ledger` | `owner_ledger.view` | All owners, filterable |
| `GET /owner-ledger/{owner_id}` | `owner_ledger.view` | One owner's ledger, paginated |
| `GET /owner-ledger/{owner_id}/balance` | `owner_ledger.view` | Current balance + outstanding recoverable expenses |
| `GET /owner-ledger/{owner_id}/dashboard` | `owner_ledger.view` | Added — the spec's "OWNER DASHBOARD" section has no other way to be reached via the API |
| `POST /owner-ledger/recoverable-expense` | `owner_ledger.create` | |
| `POST /owner-ledger/recovered-payment` | `owner_ledger.create` | |
| `POST /owner-ledger/{entry_id}/reverse` | `owner_ledger.edit` | Added — the spec's own "AUDIT" section ("only reversal entries are allowed") otherwise has no way to be reached via the API |
| `GET /owner-statement/{owner_id}` | `owner_ledger.view` | Query params: `date_from`, `date_to` |

## Testing

`backend/tests/test_owner_ledger_engine.py` — recoverable expense creation (incl. never posting as `EXPENSE`), owner reimbursement, running-balance correctness across a mixed sequence of entry types (verified two ways: the stored balance *and* `OwnerBalanceService.recompute_and_verify()`, an independent from-scratch recomputation), single-sided-entry validation, reversal (append-only, no mutation, duplicate-reversal rejection), audit logging, statement generation (cross-checked against the stored balance), the dashboard, the full API workflow, and permission enforcement.

## Explicitly out of scope for this phase

- **Profit Center / Analytics** — per the spec's own instruction. No property-level P&L attribution logic was added; `AccountingReportService`'s existing Profit Center reports (Phase 11) are untouched and not extended.
- **Automatic tenant-rent-to-owner allocation** — `RENTAL_INCOME`/`MANAGEMENT_FEE` entries can be posted (manually, via `POST /owner-ledger`, or programmatically), but this phase does not build automatic "X% of every tenant invoice becomes owner rental income minus a management fee" logic, since that's a Profit Center–level attribution decision explicitly excluded above.
- **A settlement API endpoint** — `owner_settlement_service.py`'s `OwnerLedgerSettlementService` exists and is fully usable from Python; no new router endpoint was added for it, since the spec's own requested API surface doesn't include one.
