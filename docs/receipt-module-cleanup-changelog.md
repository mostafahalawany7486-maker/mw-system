# Receipt Module Cleanup

Full audit (tables, models, services, APIs, pages, reports, printing,
PDF generation, accounting links, payment workflow, permissions) found
**two** receipt-related things in the system, not one:

1. **Rental Receipt Module** (`RentalPaymentInstallment.receipt_number`,
   `RentalService`, `RentalReceiptPrintPage.tsx`) — the tenant-facing,
   letterheaded, printed document (RR-xxx) built/redesigned in the
   previous two phases.
2. **Financial ledger `Receipt`** (`app/models/financial.py::Receipt`,
   `FinancialService`, a plain list tab in `FinancialPage.tsx`) — an
   auto-issued, read-only proof-of-payment stub (RCP-xxx) for
   `tenant_payment`/`owner_payment` transactions.

## Verdict: not a duplicate module — but one real duplicate-numbering bug

The financial `Receipt` has no printing, no PDF generation, no dedicated
permission, and no menu of its own — it's a lightweight ledger stub, not
a competing enterprise receipt system. It's the *sole* receipt for two
workflows the Rental Receipt Module doesn't cover at all: **owner
payouts** and **Rent Billing Engine invoice payments**. Both were kept
unchanged.

The one genuine conflict: confirming payment on a Rental Receipt
installment routes through the same `create_transaction()` that
auto-issues a financial `Receipt` for any `tenant_payment` — so **one
real rental payment was producing two receipt numbers** (RR-xxx, always
printed/shown to the tenant, and a silent RCP-xxx nobody ever saw).

## Fix
- `FinancialService.create_transaction()` now skips auto-issuing a
  ledger `Receipt` specifically when the transaction carries a
  `rental_installment_id` — that payment's receipt is already the RR-xxx
  document. Owner payments and invoice payments are untouched (neither
  sets `rental_installment_id`).
- `_attach_transaction_extras()` falls back to the linked
  `RentalPaymentInstallment.receipt_number` when no ledger `Receipt`
  exists, so the Financial → Transactions list still shows a correct
  receipt number — the single real one, not a blank.
- `FinancialPage.tsx`'s Receipts tab description updated to state its
  actual (now-correct) scope: owner + invoice payments, pointing to
  Rentals → Receipts for rental tenant payments.

## Tests added
- Confirming a rental payment creates **no** new financial `Receipt` row
  and the transaction correctly shows the RR-xxx number.
- Owner payments still get their own RCP-xxx receipt, unaffected.
- (Pre-existing) invoice payment test already covered that path staying
  untouched.

**Not executed** — same standing caveat: statically reviewed and
`py_compile`/brace-balance checked only, no network access to run
`pytest`/`npm` in this sandbox.
