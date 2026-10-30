# Rental Receipt — Design & Approval Phase

Changelog for this phase. Reused the existing Rental Receipt module end
to end — no new module, route, table, or page was created.

## Integration point (unchanged)
- Frontend: `frontend/src/pages/RentalReceiptPrintPage.tsx`
  (`/rentals/receipts/:installmentId/print`)
- Backend: `RentalService.get_receipt_document()` →
  `GET /rentals/installments/{id}/receipt`

## Design process
3 concepts were designed and presented for approval (Ledger Line, Mirror
Split, Boxed Card Grid) as a standalone HTML mockup, each at correct
physical print dimensions, before any implementation. **Approved:
Concept B — Mirror Split.** Quarter A4 was explicitly scoped out for
this pass (kept as a documented future addition, not built).

## What changed

### Page size
- `PAGE_SIZES.half` corrected from 210×148mm (ISO A5 landscape) to the
  spec's actual **297×105mm** ("two receipts stacked on one A4 landscape
  sheet" convention, for pre-cut letterhead stock — not a standard ISO
  half-cut). `full` (plain A4 landscape) kept as a pre-existing fallback
  for printers without pre-cut paper. `quarter` removed for now.

### Layout (Concept B — Mirror Split)
- Sheet is split into two independent, fully-mirrored halves by a thin
  vertical rule: Arabic (RTL) on the right, English (LTR) on the left —
  each with its own complete field list and signature footer, rather
  than dual-language labels on every line. No logo/company header
  (letterhead-safe, unchanged). No payment status anywhere, per spec.

### New data wired into the receipt
- **Tenant Address** — was previously always blank (`Tenant` had no
  address column at all). Added `Tenant.address` (migration `0017`,
  free-text — this is only ever a single printed line, not
  filtered/geocoded the way Property/Owner addresses are), exposed in
  the tenant create form and detail page.
- **Payment Method / Bank Name / Reference Number (doubles as Cheque
  Number)** — no new columns duplicated. `payment_method` and
  `reference_number` were already synced onto the installment by the
  existing `confirm_payment` → `FinancialService.create_transaction()`
  flow; the receipt now reads them directly. `bank_name` isn't stored on
  the installment or the Transaction (it only exists on
  `FinancialAccount`), so one lookup resolves the confirming
  Transaction → its account → `bank_name`. All three are correctly
  `None`/blank on a receipt printed before payment is confirmed (this
  system's normal "generate before payment" workflow) — this is expected
  behavior, not a bug.

### Bug caught mid-implementation
- First pass wrote `bank_name` as if it were a `Transaction` column —
  it isn't (`Transaction` has no `bank_name` field; it's a
  `FinancialAccount` field). Caught and fixed via `account.bank_name`
  before this shipped, with a test covering it
  (`test_receipt_document_shows_bank_name_after_bank_transfer_confirmation`).

## Testing
Added: payment-blank-before-confirmation, cash/bank_transfer/cheque
receipt field assertions. The pre-existing
`test_receipt_document_excludes_forbidden_fields_and_includes_required_ones`
test — which already asserted a real `tenant_address` value and was
failing before this phase (no `Tenant.address` column existed) — should
now pass.

**Not executed** — same standing caveat as the rest of this project: no
network access in the build sandbox to install FastAPI/pytest or run
`npm`. Statically reviewed and `py_compile`/brace-balance checked only.
Run `alembic upgrade head` and `pytest` before deploying.
