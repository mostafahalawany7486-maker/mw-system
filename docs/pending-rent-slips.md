# Pending Rent Slips (printed before collection)

## The real-world workflow this solves

At the start of each month, print a rent slip and hand it to the
building guard, who gives it to the tenant. When the guard later
confirms the tenant actually paid, the owner comes back to the system
and registers the real collection. Until then, nothing should be
counted as collected.

## Why this is a new, separate concept, not a change to Rent Vouchers

`RentVoucher` (Phase 15/19) has one deliberate, load-bearing guarantee:
a voucher only exists because a real `Transaction` already exists (see
its own docstring — "the spec is explicit this is tied directly to a
Transaction," enforced by a `NOT NULL transaction_id` and a unique
constraint). Every report, audit check, and piece of documentation
written about that module assumes that guarantee holds. Loosening it
to allow a transaction-less voucher would weaken that guarantee for
every existing caller, not just this new use case.

`PendingRentSlip` is a new table upstream of that guarantee instead —
same visual output, same numbering-style pattern, same tenant/company
copy pair, but explicitly *not* a `RentVoucher` until collection is
confirmed. **`RentVoucher` itself was not modified at all.**

## The three steps

1. **Generate** (`POST /pending-rent-slips/generate`) — pick a building
   and a rental month; every currently-active `RentalContract` in that
   building gets a slip *pair* (tenant + company copy), using each
   contract's current `rent_amount` as the expected amount. Creates
   **no** Transaction, touches **no** `RentVoucher`.
2. **Print** — identical rendering to a real voucher, on purpose:
   `RentVoucherPrintPage.tsx` gained a `?source=pending` mode that
   points the same `VoucherSlot` component at
   `/pending-rent-slips/print-data/bulk` instead of
   `/rent-vouchers/print-data/bulk` — zero visual differences, since
   both endpoints return the exact same DTO shape
   (`PendingSlipPrintDataOut` mirrors `RentVoucherPrintDataOut` field
   for field). Payment-method checkboxes print blank (nothing selected
   yet), same as an unpaid voucher would.
3. **Confirm Collection** (`POST /pending-rent-slips/{id}/confirm-collection`)
   — the *only* place this module creates anything real. It calls the
   existing, unmodified `FinancialService.create_transaction()` (same
   as a human using Financial → Record Transaction) and then
   `RentVoucherService.generate_vouchers()` (same as Rent Vouchers →
   Generate) — never reimplementing either. The slip pair is marked
   `collected`, linked to the resulting transaction, and the caller is
   handed the real voucher IDs to print as the final receipt.

## Safety / non-duplication

- Reuses existing permissions only: `rent_vouchers.view/create/edit`
  for slip management, `financial.create` for confirming collection
  (since that's functionally "record a payment"). No new permission
  module.
- A `UniqueConstraint(tenant_id, property_id, rental_month, copy_type)`
  prevents ever generating two pending slips for the same tenant in
  the same month for the same unit — generation is idempotent, same
  pattern as `RentVoucherService.generate_vouchers`.
- The workflow-state column is named `slip_status`, not `status` —
  `BaseModel` already has a `status` column for the shared
  active/archived concept (see the Archive extension); reusing it here
  would have silently overloaded that column with a second, unrelated
  meaning.

## Not tested by running the app

No network access in this environment to install dependencies or run
migrations. Every file was syntax-checked and every reused
service/field was verified against its actual source. Before relying
on this: run `alembic upgrade head`, generate slips for a building,
print them, confirm collection, and verify the resulting real voucher
prints correctly and the transaction appears in Financial.
