# Financial Engine (Phase 19)

## Pre-implementation analysis

The spec's own framing — "manages operational financial balances before
accounting entries are generated; accounting remains responsible only
for journal entries and the General Ledger" — describes something that
**already substantially exists** in this codebase. Before writing any
code, every requested piece was checked against what's already there:

| Spec asks for | Already exists |
|---|---|
| Company/Owner/Tenant Ledger + automatic balances | `Transaction` (Phase 8, unified ledger table) + `FinancialAccount.current_balance()` + `outstanding_balances()` — computed live, never stored |
| Recoverable Expense / Recovered Amount / Owner Payment | **Literally the Owner Ledger Engine (Phase 17)**, same transaction type names |
| Tenant Payment / Refund / Allocation | **Literally the Payment & Collection Engine (Phase 16)** |
| Discount / Late Fee | Fields already on `RentalContract` (Phase 7) |
| Internal Transfer | `TransactionType.TRANSFER_IN/OUT` + `FinancialService.create_transfer()` (Phase 8), balance-checked, complete |
| Manual Correction / reversal-only | `JournalEntryService.reverse_entry` + `OwnerLedgerService.reverse_entry` (Phase 17) |
| Company Cash / Tenant Outstanding / Today's & Monthly Collections | `FinancialService.dashboard()` already computes most of this |
| Building/Property Financial Summary | Partially exists via the Property Profit Center (Phase 11) |
| "Accounting via events, never directly" | Already how this codebase works: `create_transaction()` triggers `JournalEntryService.auto_post_from_transaction` as a decoupled hook the caller never touches directly |
| **Security Deposit lifecycle** | **Genuinely missing.** `RentalContract`/`LeaseAgreement.security_deposit_status` (Phase 3/7) are single fields nothing ever transitions — confirmed by grep before writing anything: the only existing reference (`lease_workflow_service.py`) literally warns *"settle it via the security deposit workflow/endpoint"* for a workflow that was never built. |

## The core decision: six ledgers, one source of truth

Building six separate physical ledger tables (Company/Owner/Tenant/
Building/Property/Unit) would mean six copies of overlapping data that
could drift out of sync with each other — which **is** the "ledger
imbalance" the spec explicitly asks to prevent. Instead:

- **Company, Tenant, Building, Property, Unit Ledger** — live views,
  computed on every read, over `Transaction` (`balance_service.py`).
  "Unit Ledger" and "Property Ledger" run the literal same query — a
  unit *is* a `Property` row in this codebase (Phase 4/5 design); kept
  as two methods only because the spec names them separately.
- **Owner Ledger** — delegates directly to `OwnerBalanceService`
  (Phase 17, unchanged). Not re-implemented.

This is also the answer to `ledger_sync_service.py`'s spec requirement
("prevent ledger imbalance"): there is no synchronization problem to
solve by construction, since nothing here is a second copy of anything.
That file is instead an honest integrity *check* on the one place a
running total genuinely is stored (see below).

## The one new table: `DepositLedgerEntry`

A single `amount` + `status` field can't represent a deposit's real
history (received 1000, partially refunded 600, deducted 150 for
damage, forfeited the remaining 250) — so this phase adds one new,
append-only table (`deposit_ledger_entries`, migration `0023`): one row
per lifecycle action (Received, Partial Refund, Full Refund, Deduction,
Forfeit, Transfer to Owner), each carrying the resulting remaining
balance (`balance_after`) — the same "store the running total" pattern
`OwnerLedgerEntry.balance` already established in Phase 17.

`RentalContract`/`LeaseAgreement.security_deposit_amount`/`_status`
(Phase 3/7) are **not removed or restructured** — they remain the
"current snapshot" (original amount, current status), kept in lockstep
by `deposit_service.py`; `DepositLedgerEntry` is the full history behind
that snapshot.

**Which actions create a real `Transaction`, and which don't:**

| Action | New `Transaction`? |
|---|---|
| Received | Yes — `DEPOSIT_RECEIVED` |
| Partial / Full Refund | Yes — `DEPOSIT_REFUND` |
| Deduction | **No** — the cash is already in a company account from the original Received transaction; a deduction only reduces how much of it is still owed back, which is bookkeeping, not a new cash movement |
| Forfeit | No, same reasoning |
| Transfer to Owner | No new `Transaction`, but posts a real `OwnerLedgerEntry` credit (Phase 17, reused directly) — the money is now owed to the owner |

## Conflicts found, and the safest solution for each

### Conflict 1 — the spec's `/financial/...` API paths collide with the existing financial router

`app/api/v1/routers/financial.py` (Phase 8, unmodified) already owns
the `/financial` prefix, including its own `/financial/dashboard` and
`/financial/transfers`. Mounting a second router at the exact same
prefix with colliding sub-paths would silently shadow whichever handler
FastAPI happens to match first — a direct violation of "DO NOT break
existing APIs."

**Safest solution:** the new router is mounted at `/financial-engine`
instead. Every operation the spec's API section asks for is still
present, under a prefix that structurally cannot collide with the
pre-existing one. Confirmed no collision exists anywhere by listing
every registered router prefix in the whole API before finalizing this.

### Conflict 2 — "Prevent duplicate transactions" needed a query that didn't exist

`TransactionRepository` had no `get_by_reference_number`, unlike
`PaymentRepository` which already has the equivalent. Added as one
small, additive method (`financial_repository.py`), mirroring
`PaymentRepository.get_by_reference_number`'s exact pattern — not a new
duplicate-detection mechanism, the same one Phase 16 already
established, extended to the one table that didn't have it yet.

### Conflict 3 — a tenant-side "Adjustment" had no `TransactionType` to use

`TransactionType` (Phase 8) had no `ADJUSTMENT` value. Added as one new,
purely additive enum member (`app/models/financial.py`) — existing
values unchanged, same safe pattern already used twice before for
`RECOVERABLE_EXPENSE`/`OWNER_REIMBURSEMENT` (Phase 17). Not added to the
raw `/financial/transactions` endpoint's accepted values, so a tenant
adjustment can only be created through this module's own dedicated
service — the same "paired write, no loose rows" discipline Phase 17
established for its own new transaction types.

### Conflict 4 — Owner-side Financial Engine reused, not duplicated

`allocation_service.py`, `refund_service.py`, and `adjustment_service.py`
are deliberately thin: they validate against this module's own rules
(`financial_validator.py`) and then delegate the actual work to
`PaymentWorkflowService` (Phase 16) or `OwnerLedgerService` (Phase 17)
— confirmed correct by checking each target method's exact signature
before wrapping it (this caught two real bugs during development: a
wrong parameter order calling `refund_payment`, and a fully duplicated
reimplementation of `create_transfer` that already existed correctly in
`FinancialService` — both fixed before this module shipped).

## API

Mounted at `/financial-engine` (see Conflict 1). All financial data
operations require the existing `financial.view`/`financial.create`/
`financial.edit` permissions (Phase 8) — no new permission module was
added, since this is the same financial domain, not a separate one.

| Method & path | Notes |
|---|---|
| `GET /financial-engine/ledgers` | Portfolio-wide summary (Company Ledger — the only one of the six that isn't scoped to a specific entity) |
| `GET /financial-engine/company` | |
| `GET /financial-engine/owners/{owner_id}` | Delegates to `OwnerBalanceService` |
| `GET /financial-engine/tenants/{tenant_id}` | |
| `GET /financial-engine/buildings/{building_id}` | |
| `GET /financial-engine/properties/{property_id}` | |
| `GET /financial-engine/units/{unit_id}` | Same query as `/properties/{id}` — see "core decision" above |
| `GET /financial-engine/dashboard` | Company Cash, Owner/Tenant Outstanding, Security Deposits Held, Recoverable Expenses, Recovered Amounts, Today's/Monthly Collections |
| `POST /financial-engine/deposit` | Receive a security deposit |
| `GET /financial-engine/deposits/{contract_type}/{contract_id}` | Full history + current remaining balance |
| `POST /financial-engine/deposits/{contract_type}/{contract_id}/deduct` | Added — otherwise unreachable |
| `POST /financial-engine/deposits/{contract_type}/{contract_id}/forfeit` | Added — otherwise unreachable |
| `POST /financial-engine/deposits/{contract_type}/{contract_id}/transfer-to-owner` | Added — otherwise unreachable |
| `GET /financial-engine/deposits/{contract_type}/{contract_id}/verify` | The integrity check (`ledger_sync_service.py`) |
| `POST /financial-engine/refund` | `refund_type: "payment"` (delegates to the Payment Engine) or `"deposit"` |
| `POST /financial-engine/adjustment` | `scope: "owner"` or `"tenant"` |
| `POST /financial-engine/transfer` | Delegates entirely to the existing `FinancialService.create_transfer()` |

## Receipt System — untouched, as instructed

Nothing in this phase touches receipt numbering, QR/barcode generation,
bilingual printing, or K-Net integration. `DEPOSIT_RECEIVED`/
`DEPOSIT_REFUND` transactions flow through the exact same
`FinancialService.create_transaction()` every other transaction type
already uses — the existing Receipt System (wherever it hooks into
`Transaction`) is unaffected because nothing about that integration
point changed.

## Testing

`backend/tests/test_financial_engine.py` — the full deposit lifecycle
(received → partial refund → full refund; received → deduction;
received → forfeit; received → transfer to owner), every VALIDATIONS
rule (duplicate deposit, negative deposit, over-refund, duplicate
transaction reference, invalid allocation sum), the deposit ledger
integrity check, all six ledger views, owner and tenant adjustments,
the full API workflow (deposit → summary → verify → dashboard →
transfer), and permission enforcement.

## Explicitly out of scope (per the spec's own instruction)

- **Analytics, Profit Center, or any dashboard outside this module** —
  the existing Property Profit Center (Phase 11) and Enterprise
  Dashboard are untouched and not extended.
- **A real message broker / event bus for accounting integration** —
  the existing decoupled-hook pattern (`auto_post_from_transaction`)
  already satisfies "publish events, don't create GL entries directly"
  in practice; building actual pub/sub infrastructure for it would be
  new infrastructure this stack has never had anywhere, for a
  requirement the existing hook already fulfills honestly.
- **Rewriting `PropertyService`'s existing building-summary aggregation
  onto this module** — that older code path (Phase 2.0/11) is untouched
  and still works exactly as before.

**STOP AFTER THIS PHASE — per the spec's own instruction, no further
module was started beyond what's documented here.**
