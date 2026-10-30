# Payment & Collection Engine (Phase 16)

## Pre-implementation analysis

| Area | Finding |
|---|---|
| **Current payment recording** | `FinancialService.create_transaction()` (`transaction_type=tenant_payment`) is the existing single-step "record a payment" mechanism, wrapped by `FinancialService.record_invoice_payment()` for the Rent Billing Engine's `Invoice`, and by `RentalService.confirm_payment()` for the older Rental Receipt Module's `RentalPaymentInstallment`. Both post immediately, with no verification step and no first-class "Payment" record of their own. |
| **Rental contracts / tenant management** | Unchanged. `Payment.tenant_id`/`rental_contract_id` reference `Tenant`/`RentalContract` read-only. |
| **Property management** | Unchanged. Building/unit resolution reuses the existing `Property.parent_property_id` hierarchy (same pattern as Phases 14/15). |
| **Payment & accounting transactions** | `Transaction`, `Invoice`, `Receipt`, `JournalEntry` (Phases 8/10) are the ledger of record and are **not** replaced — `Payment` posts through them, never around them. `JournalEntryService.reverse_entry()` already exists and does exactly what a proper accounting reversal requires (a mirror-image reversing entry, never deleting a posted one) — reused unchanged for `/reverse`. |
| **Existing user permissions/roles** | Extended the existing `module.action` catalog (`payments.view/create/edit`), same as every other module. |

## The conflict this analysis found, and the safest solution

**The conflict:** the spec's status list (`Pending, Verified, Partially Paid, Paid, ...`) and its requirement to support **partial payment** implies a Payment can be captured before it's posted, and can be paid in installments against whatever it's for. The existing system has *two* different "pay against X" engines:

1. **Invoice** (Rent Billing Engine) — `amount_paid` accumulates correctly across multiple partial payments; status becomes `PARTIALLY_PAID` then `PAID`. Already correct.
2. **RentalPaymentInstallment** (Rental Receipt Module) — `FinancialService.create_transaction()`'s installment-sync always sets `payment_status = "paid"` unconditionally the moment *any* transaction links to it, full stop. It was never designed for partial payment.

Building the new Payment engine's "receipt" targeting on top of (2) would require changing that shared sync logic inside `create_transaction()` — but that function is called by every other payment-recording path in the system (`confirm_payment`, `record_invoice_payment`'s own transaction creation, owner settlements, etc.). Changing it risks silently breaking all of them, which the rules explicitly prohibit ("do not modify existing functions unless absolutely required," "do not break existing APIs").

**The safest solution — and the one implemented:** `Payment`/`PaymentAllocation` target **`Invoice`**, not `RentalPaymentInstallment`. Invoice's partial-payment model is already correct and already exactly what the spec needs; targeting it required zero changes to any existing file. The spec's suggested `receipt_id` field is `PaymentAllocation.invoice_id` in this implementation — an Invoice **is** the payable "receipt to be paid" in this codebase's own Rent Billing Engine terminology (`InvoiceStatus.SENT` is commented `# "Issued" in Rent Billing Engine terminology`). The older Rental Receipt Module is completely untouched and keeps working exactly as it did.

**A second, smaller conflict, same resolution pattern:** an earlier phase (Phase 12) already had a class named `PaymentWorkflowService` — a much simpler, single-step wrapper around `record_invoice_payment()` with no capture/verify/refund/reverse lifecycle. Since this phase's engine is a strict superset of that capability, keeping both would mean two classes with the same name doing overlapping things — exactly the "duplicate business logic" the rules prohibit. The old one was retired (`app/business_workflows/payment_workflow_service.py` and its tests deleted), the same way an even earlier flat `rent_cycle_workflow_service.py` was retired when the dedicated Rent Cycle Engine (Phase 14) superseded it. See `app/business_workflows/__init__.py`'s docstring and `docs/business-workflows.md` for both.

## Two-phase lifecycle

```
Create Payment (Pending)
   │  data captured: tenant, account, method, amount,
   │  one-or-more (invoice_id, amount) allocations.
   │  NOTHING posts to the ledger yet.
   │  Validated eagerly: amount > 0, unique reference_number,
   │  amount == sum(allocation amounts), every allocation target
   │  is a payable (not cancelled/void/already-paid) Invoice with
   │  enough outstanding balance.
   ▼
Verify ──► for each allocation, calls the EXISTING
   │        FinancialService.record_invoice_payment() unchanged —
   │        this is where the Transaction is created, the Receipt
   │        is auto-issued, and the JournalEntry auto-posts.
   │        Re-validates each allocation against Invoice's CURRENT
   │        outstanding balance (defense in depth — outstanding
   │        balance could have changed since Create).
   ▼
Verified / Partially Paid / Paid   (derived from each allocated
   │                                 Invoice's own resulting status)
   │
   ├──► Refund ──► new REFUND-type Transaction via
   │               FinancialService.create_transaction (unchanged);
   │               proportionally rolls back amount_paid on the
   │               affected invoice(s) — the one genuinely new piece
   │               of business logic in this module (record_invoice_
   │               payment has no "undo" of its own).
   │
   └──► Reverse ─► finds each allocation's posted JournalEntry
                   (via source_transaction_id) and calls the
                   EXISTING JournalEntryService.reverse_entry()
                   unchanged — a proper mirror-image reversing entry,
                   never a delete. Also rolls back amount_paid
                   (same reasoning as Refund). Blocked if already
                   reversed (see "Prevent duplicate reversal" below).

Cancel — PENDING only, before anything posts. No ledger effect to
         undo, so this is a pure status change plus an audit record.
```

## New database tables

Two new tables, additive only — `tenants`, `properties`,
`rental_contracts`, `invoices`, `financial_accounts`, and
`transactions` are **not modified**. See `app/models/payment.py`.

### `payments`
| Column | Notes |
|---|---|
| `id`…`updated_by` | Standard audit columns |
| `payment_number` | `PAY-000001`, sequential, unique |
| `tenant_id` | FK → `tenants.id`, required |
| `rental_contract_id`, `property_id` | FK, nullable — the spec's "lease_id" maps to `rental_contract_id` (the tenant-side contract; see the naming note below) |
| `account_id` | FK → `financial_accounts.id` — required to actually post at verify time; not in the spec's suggested list but essential |
| `payment_method` | cash / knet / bank_transfer / cheque / online / **mixed** (mixed is new — see "Payment methods" below) |
| `payment_date`, `amount`, `currency`, `reference_number`, `notes` | As specified. `currency` is a snapshot of the account's currency at capture time (same "must stay correct forever" reasoning as `Invoice.snapshot`) |
| `payment_status` | pending / verified / partially_paid / paid / cancelled / refunded / reversed |
| `cancellation_reason`, `refund_reason` | Set on the corresponding transition |
| `verified_at`, `refunded_at`, `reversed_at` | Timestamps |

`owner_id`/`owner_name`/`building_name` are **read-only computed
properties**, resolved through `property_id → Property.owner`/`.parent`
— never stored columns, and never used to drive any owner-side logic,
per the spec's own "Do not implement Owner Accounting in this phase."

### `payment_allocations`
One row per Invoice a Payment covers — this is what makes "one payment
covering multiple receipts" possible. `UNIQUE(payment_id, invoice_id)`.

| Column | Notes |
|---|---|
| `payment_id` | FK → `payments.id`, `ON DELETE CASCADE` |
| `invoice_id` | FK → `invoices.id` |
| `amount` | This allocation's portion of the payment |
| `transaction_id` | FK → `transactions.id`, nullable until `verify()` posts it |

Migration: `app/alembic/versions/0020_payment_collection_engine.py`.

## Payment methods

`cash`, `bank_transfer`, `cheque`, `online`, `knet` already existed in
`VALID_PAYMENT_METHODS` (`app/schemas/financial.py` / `rental.py`) —
**nothing changed there**. `mixed` is new and lives *only* in this
module's own `PaymentMethod`/schema validator — it describes the
Payment as a whole when more than one underlying method was actually
used to collect it. Each individual allocation still posts through
`record_invoice_payment()` with the Payment's single overall
`payment_method` value (the existing engine has no per-allocation
payment method field); a payment genuinely split across different
methods per invoice is a natural extension (adding an optional
`payment_method` override to `PaymentAllocationIn`) left for a later
phase, since the spec's own suggested `Payment` schema also only has
one `payment_method` field for the whole record.

## Validations (per spec)

| Rule | Where enforced |
|---|---|
| Negative payments | `PaymentValidator.validate_amount_positive` (create) + Pydantic field validators (API) |
| Duplicate reference numbers | `PaymentValidator.validate_unique_reference_number` (create) |
| Payment exceeding allowed amount | `PaymentValidator.validate_allocation_target` — checked against `Invoice.outstanding_amount` at create **and** re-checked at verify (the balance may have moved) |
| Payment on cancelled receipts | Same method — rejects `CANCELLED`/`VOID`/already-`PAID` invoices |
| Duplicate reversal | `PaymentValidator.validate_can_reverse` — `DuplicateReversalError` if already `REVERSED` |
| `amount == sum(allocations)` | Enforced twice — `PaymentCreate.validate_amount_matches_allocations` (API/Pydantic) **and** `PaymentValidator.validate_allocations_sum_matches_amount` (service layer, so a direct/non-API caller can't bypass it) |

## Automatic operations (per spec), and what actually does them

| Spec requirement | Implementation |
|---|---|
| Update Receipt | Free, via `record_invoice_payment()`'s existing auto-issued `Receipt` — unchanged |
| Update Lease Balance | `Invoice.outstanding_amount` recalculates live (`amount - amount_paid`) — no stored balance to go stale |
| Update Tenant Balance | `FinancialService.outstanding_balances()` (unchanged) reused in the dashboard |
| Update Dashboard | New `PaymentWorkflowService.dashboard()` — see below |
| Trigger Accounting Event | Free, via `record_invoice_payment()`'s internal `create_transaction()` → `JournalEntryService.auto_post_from_transaction` — unchanged |
| Create Audit Record | `AuditService.log_activity`/`log_audit` on every transition — same pattern as every other module |

## Collection Dashboard (`GET /payments/dashboard/summary`)

| Metric | Source |
|---|---|
| Collected Today / This Month | `PaymentRepository.sum_collected_between()` — sums completed `TENANT_PAYMENT` transactions in range (reads the ledger directly, the single source of truth for what was actually collected — not `Payment.amount`, which can include not-yet-verified amounts) |
| Outstanding Balance | `FinancialService.outstanding_balances()["total_tenant_outstanding"]` — reused, unchanged |
| Overdue Amount | Sum of `Invoice.outstanding_amount` where `invoice_status == OVERDUE` (a status the existing `maintenance_sweep()` already sets — read-only here) |
| Collection Percentage | `collected_this_month / (collected_this_month + total_outstanding) × 100` |

## API (`/api/v1/payments`)

| Method & path | Permission |
|---|---|
| `POST /payments` | `payments.create` |
| `GET /payments` | `payments.view` (filter: `tenant_id`, `payment_status`, `payment_method`, `date_from`, `date_to`) |
| `GET /payments/{id}` | `payments.view` |
| `POST /payments/{id}/verify` | `payments.edit` |
| `POST /payments/{id}/cancel` | `payments.edit` |
| `POST /payments/{id}/refund` | `payments.edit` |
| `POST /payments/{id}/reverse` | `payments.edit` |
| `GET /payments/dashboard/summary` | `payments.view` |

## Testing

`backend/tests/test_payment_collection_engine.py` — capture (full,
partial, multi-invoice allocation), every validation rule above,
verify (status derivation, ledger posting), cancel, refund
(incl. `amount_paid` rollback), reversal (incl. duplicate-reversal
rejection and `amount_paid` rollback), the collection dashboard, the
full API workflow, and permission enforcement.

## Explicitly out of scope for this phase

- **Owner Accounting** — per the spec's own instruction. `owner_id`/
  `owner_name` on `Payment` are read-only display fields; no owner
  payout/settlement logic was added or changed (see
  `OwnerSettlementWorkflowService`, Phase 12, for the existing —
  separate, untouched — owner payout capability).
- **Per-allocation payment method** for true multi-method "mixed"
  payments — see "Payment methods" above.
- **Scheduler wiring** — every endpoint here is on-demand, consistent
  with every other batch/lifecycle operation in this codebase.
