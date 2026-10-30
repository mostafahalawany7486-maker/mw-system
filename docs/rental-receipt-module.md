# Rental Receipt Module

## Phase 1 recap (approved before implementation began)

Full original analysis is preserved in conversation history; the four
open decisions were resolved with the stated lowest-risk defaults:

1. **Arabic RTL rendering**: browser-rendered/printed HTML, not a
   server-generated PDF — reuses the app's existing i18n/RTL support end
   to end instead of adding bidi-shaping libraries (`python-bidi`,
   `arabic-reshaper`) to the PDF engine.
2. **Bank/cheque reference fields**: packed into the existing
   `reference_number` column with a documented convention (see below),
   rather than adding dedicated columns.
3. **Permissions**: reused existing `rentals.*`/`financial.*` rather
   than adding a new `receipts` permission module.
4. **Monthly generation**: a manual "Generate Monthly Receipts" trigger
   (`POST /rentals/receipts/generate-monthly`), consistent with the
   existing `run_maintenance_sweep()` pattern — no scheduler exists in
   this codebase, and none was added.

## Architecture — what's new vs. what's reused

**Reused unchanged:**
- `RentalPaymentInstallment` — the existing monthly schedule table
  *is* the receipt record. No new "receipt" entity was created.
- `FinancialService.create_transaction()` — Confirm Payment's entire
  backend is one call into this existing method (property attribution,
  installment-status sync, GL auto-posting, and auto-issuing the
  existing proof-of-payment `Receipt` model all already happen inside
  it, untouched).
- `Property` hierarchy (`parent_property_id`) for Building/Unit.
- `Tenant.address`, `RentalContract.tenant_display_name`/
  `property_title` computed properties.
- `ActivityLog`/`AuditLog` for the full audit trail — no new audit
  infrastructure.
- `Role`/`Permission`/`PermissionChecker` — zero new permission rows.
- The existing sequential-numbering pattern (`COUNT()+1`, same shape as
  `TXN-`/`RCP-`/`INV-`) for the new `RR-` prefix.
- The app's existing i18n Arabic RTL support and `@media print` CSS
  infrastructure, for the printable document itself.

**New (additive only):**
- Migration `0013`: three nullable/defaulted columns on
  `rental_payment_installments` (`receipt_number` unique indexed,
  `printed_at`, `print_count` default 0). No existing column touched.
- `app/core/number_to_words.py` — English + Arabic amount-in-words.
  Self-contained, no dependencies.
- `knet` added to `VALID_PAYMENT_METHODS` (one-line, additive).
- ~10 new methods across `RentalInstallmentRepository`/`RentalService`
  (all in the *existing* files for this module, not new ones).
- 6 new endpoints under the *existing* `/rentals` router.
- Two new frontend pages (`RentalReceiptsPage`, `RentalReceiptPrintPage`)
  plus one new nav entry point (a button on the existing Rentals page,
  following the exact pattern already used for the Maintenance
  Directory sub-page).

## Data model

`RentalPaymentInstallment` (existing table, extended):

| Column | Type | Notes |
|---|---|---|
| `receipt_number` | `varchar(20)`, unique, nullable | `RR-000001` sequence. Null until "Generate Monthly Receipts" runs for that installment's month. |
| `printed_at` | `timestamptz`, nullable | Set on every print/reprint. |
| `print_count` | `int`, default 0 | Incremented on every print/reprint. |

Everything else the receipt needs already existed: `due_date` (=
rental month), `amount`/`discount_amount`/`tax_amount`/
`late_fee_amount`/`total_payable`, `payment_status`, `paid_date`,
`payment_method`, `reference_number`, plus the `contract` relationship
chain to `tenant`/`property`/`property.parent` (building).

**Reference number convention** (decision #2 above — no new columns):
- Bank transfer: `"<Bank Name> — <reference>"`, e.g. `"NBK — TRF20394"`.
- Cheque: the cheque number alone, e.g. `"CHQ-004821"`.
- K-NET: the K-NET transaction reference alone.
- Cash: left blank.

This is enforced by convention/UI hint text, not a database constraint
— consistent with how `reference_number` is already used unconstrained
elsewhere in this codebase.

## API reference

All under the existing `/rentals` router/permission scheme.

| Endpoint | Permission | Purpose |
|---|---|---|
| `POST /rentals/receipts/generate-monthly` | `rentals.create` | Body: `{year, month}`. Assigns `RR-` numbers to installments due that month for active leases that don't already have one. Idempotent. |
| `GET /rentals/receipts/search` | `rentals.view` | Filters: `receipt_number`, `tenant_id`, `property_id`, `rental_month` (`YYYY-MM`), `date_from`/`date_to`, `payment_method`, `reference_number`. Only returns installments that already have a receipt number. |
| `GET /rentals/installments/{id}/receipt` | `rentals.view` | The printable document DTO — tenant name/address, building/unit name+number, amount, amount-in-words (EN+AR). Never includes phone/civil-ID/contract-number/payment-status, per the approved content design. 409 if not yet generated. |
| `POST /rentals/installments/{id}/receipt/print` | `rentals.edit` | Increments `print_count`, sets `printed_at`, logs `receipt_printed`/`receipt_reprinted`. Never touches `payment_status` or any receipt content. |
| `POST /rentals/installments/{id}/confirm-payment` | **`financial.edit`** | Body: `account_id`, `payment_method`, `reference_number`, `transaction_date`, `notes`. The only action that creates a `Transaction` and marks the installment paid. 409 if already paid. Gated by `financial.edit` (not `rentals.edit`) to match the existing precedent set by `POST /financial/invoices/{id}/record-payment`, since both create a financial transaction. |

Frontend print route (not an API endpoint): `/rentals/receipts/:installmentId/print?copy=tenant|company&size=half|quarter|full`.

## User guide (accountant workflow)

1. Beginning of the month: **Rentals → Rental Receipts → Generate
   Monthly Receipts**, enter year/month, Generate. Safe to click more
   than once.
2. Print each tenant's copy (and the company copy, via `?copy=company`)
   from the receipt list, choosing half/quarter A4 to match your
   letterhead stock.
3. Tenant signs the **company copy**. File it.
4. When the tenant pays and you have the signed copy + payment proof in
   hand: click **Confirm Payment** on that receipt, fill in how it was
   paid, and confirm. This is the only step that posts accounting and
   updates balances — printing/reprinting never does.

## Administrator notes

- No new permission module to configure — receipt actions inherit
  whoever already has `rentals.view/create/edit` and `financial.edit`
  (Administrator and Branch Manager, out of the box; see
  `docs/permissions-matrix.md` — unchanged by this module).
- No scheduler to configure. If automatic monthly generation is wanted
  later, `RentalService.generate_monthly_receipts()` is already a plain
  callable — wiring a cron/APScheduler job to call it is additive, not
  a redesign.

## Testing

`backend/tests/test_rental_receipts.py` — 20 tests covering: monthly
generation (including idempotency and skipping draft/inactive
contracts), the printable document's field allow/deny-list, print vs.
reprint tracking (and that printing never changes payment status),
Confirm Payment's full effect (transaction creation, property
attribution, double-confirmation rejection, invalid payment method
rejection, auth requirement), search, and — per the regression
requirement — explicit tests that the pre-existing installment CRUD,
direct transaction creation, and Invoice→`record_invoice_payment` flow
are all completely unaffected.

`number_to_words.py` was additionally verified by direct execution
during development (not just unit tests) across whole numbers,
fractional amounts, the Arabic dual form (2000 → "ألفان"), and zero.

## Security

- No new attack surface: every new endpoint goes through the same
  `PermissionChecker` dependency every other endpoint in this codebase
  uses; no new authentication mechanism.
- `confirm-payment` is idempotency-protected (409 on an
  already-paid installment) — a network retry or double-click can't
  double-post accounting.
- Every state-changing action (generate, print, confirm) writes to the
  existing `ActivityLog`, which already carries `ip_address`/
  `user_agent` via `AuditLog` for anything that needs field-level diff
  tracking.
- The printable receipt route is still behind `ProtectedRoute` (auth
  required) even though it renders outside the normal app chrome.

## Performance

- `generate_monthly_receipts` runs one indexed query (`due_date` +
  `contract_status`, both already indexed columns) and touches only
  the rows that need a new receipt number — no full-table scans.
- `receipt_number` has a unique index (added by migration `0013`),
  matching the existing pattern for `TXN-`/`RCP-`/`INV-` lookups.
- `get_receipt_document`/`search_receipts` eager-load the
  contract→tenant/property chain in one query each (`selectinload`),
  avoiding N+1s — same pattern used throughout every other report/list
  endpoint in this codebase.

## Deployment notes

1. `alembic upgrade head` — applies migration `0013` (purely additive:
   two nullable columns + one column with a server-side default; safe
   on a populated production table, no data migration needed).
2. No new environment variables, no new third-party services, no new
   Docker services. `fpdf2`/`openpyxl` (already dependencies from the
   Enterprise Reporting phase) are *not* used by this module — the
   receipt itself is browser-printed, not server-rendered.
3. Restart the API process to pick up the new routes; restart/rebuild
   the frontend to pick up the two new pages and the code-split chunk
   for them (they're lazy-loaded, so they don't affect the initial
   bundle size for anyone not visiting Rentals).

## Rollback instructions

1. Revert the application code (frontend + backend) to the prior
   release.
2. `alembic downgrade -1` from `0013` — drops the three added columns
   and their index. Since they're all nullable/defaulted and nothing
   else in the schema references them via foreign key, this is a clean,
   data-loss-free rollback of *this module's* data only (no existing
   `rental_payment_installments` rows, `RentalContract` rows, or
   `Transaction` rows are affected — any transactions already created
   via Confirm Payment before the rollback remain exactly as they are,
   since they're ordinary `Transaction` rows indistinguishable from any
   other tenant payment).
