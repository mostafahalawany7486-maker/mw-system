# Rent Voucher Printing Module (Phase 15)

## Required pre-implementation system analysis

Per the spec's own "SAFETY PROCEDURE," here's what was reviewed before
writing any code, and what each review found:

| Area | Finding |
|---|---|
| **Database structure** | `Transaction` (`app/models/financial.py`) is the existing rent-payment record (`transaction_type=tenant_payment`). It already carries everything a voucher needs to reference: `tenant_id`, `property_id`, `amount`, `payment_method`, `transaction_date`, `transaction_number`. No changes needed to it. |
| **Rental contracts module** | `RentalContract`/`RentalPaymentInstallment` (Phase 7) — untouched. A voucher links to the *payment transaction*, not the contract directly, per spec. |
| **Tenant management** | `Tenant.tenant_code`, `.display_name`, `.primary_phone` already exist and are exactly the "Tenant ID / Name / Phone" fields requested. No changes. |
| **Property management** | The existing Building→Unit modeling (`Property.parent_property_id`, confirmed in Phase 1/4/5 analysis, reused again here) already gives "Building Name / Apartment Number / Property Address" via `Property.title`, `.unit_number`, `.display_location`. No changes. |
| **Payment & accounting transactions** | `payment_method` already supports `cash`, `bank_transfer`, `cheque`, **`knet`** (already present in `VALID_PAYMENT_METHODS`, `app/schemas/financial.py` / `app/schemas/rental.py` — K-Net was not missing, nothing added there). |
| **Existing PDF generation system** | `report_export_service.py` uses `fpdf2` (already a dependency) for the Enterprise Reporting PDF export — but that's for tabular financial reports, in English, with no bilingual/RTL requirement. It's the only server-side PDF generator in this codebase. |
| **Existing printing templates** | **Every printable document in this codebase today (`RentalService.get_receipt_document`, `FinancialService`'s invoice print DTOs / `_to_print_dto`) is browser-printed, not server-PDF-generated**: the backend returns a plain dict, the frontend renders the actual print layout and calls the browser's native print dialog, then calls a `record_print` endpoint to log it. There is no precedent anywhere in this codebase for a *server-rendered* PDF receipt/voucher. |
| **Existing user permissions/roles** | Confirmed the `module.action` permission catalog (`seed.py`) and `PermissionChecker` pattern — extended, not changed (see below). |

## Conflict found, and the safest solution (per rule #10)

**The conflict:** the spec requires the voucher to (a) be a proper
bilingual Arabic/English PDF and (b) "ensure Arabic characters display
correctly in PDF and printing." The only server-side PDF library
already in this project is `fpdf2`. Rendering correct Arabic in `fpdf2`
requires **contextual letter shaping and right-to-left reordering**
(Arabic letters change glyph shape based on their neighbors, and the
whole line must be reversed for correct visual order) — this needs the
`arabic-reshaper` and `python-bidi` packages. **Neither is in
`requirements.txt`, and this environment has no network access to
install them.** Generating the voucher as a server-side `fpdf2` PDF
today would produce Arabic text with disconnected letters in the wrong
visual order — worse than not shipping it, since it would silently fail
the module's own core requirement.

**The safest solution — and the one actually implemented:** follow the
pattern that already exists, successfully, elsewhere in this exact
codebase for this exact problem. The Rental Receipt Module's
`get_receipt_document()` already prints bilingual Arabic/English content
correctly *today*, in production, with zero shaping libraries — because
it never touches a PDF library at all. It returns data; the **browser**
renders the Arabic text (standard HTML `dir="rtl"` + a system/web font —
something every modern browser already does correctly, natively, with
no extra dependency), and the user's own browser print dialog ("Print to
PDF" or a physical A4 printer) produces the final output.

This module follows the identical contract:
`RentVoucherService.get_voucher_print_data()` /
`get_bulk_print_data()` return a plain, fully-bilingual dict per
voucher (`RentVoucherPrintDataOut`); `record_print()` is called by the
frontend right before invoking the browser print dialog — same shape,
same sequencing, as `RentalService.record_print` /
`FinancialService.record_invoice_print`. **No new Python dependency was
added.** The actual four-per-page A4 letterhead-compatible HTML/CSS
layout (RTL+LTR field pairs, thin borders, quarter-page height,
signature sections, checkboxes) is a frontend template — building it is
outside this backend-focused change, but the data contract it needs is
complete and documented below. If a true server-rendered PDF is wanted
later instead of/in addition to browser printing, the safe path is
adding `arabic-reshaper` + `python-bidi` to `requirements.txt` (small,
stable, widely-used libraries) and a new export function alongside
`report_export_service.py` — not modifying anything in this phase.

**Barcode, same reasoning:** no barcode-image library (e.g.
`python-barcode`) is in `requirements.txt` either. Rather than adding a
new dependency for something the browser can also do natively, the
backend computes and stores a unique `barcode_value` string
(`{voucher_number}-{transaction_number}`, e.g.
`RV-000001-TXN-000123`) containing exactly what the spec requires
("Voucher number, Transaction reference"), and documents that the
frontend renders it as an actual scannable Code128 barcode image at
print time via a standard client-side library (e.g. `JsBarcode`, a
small, dependency-free JS library — no backend change needed if a
different one is preferred). `GET /rent-vouchers/barcode/{value}` backs
"quick searching and retrieving the voucher" by scan.

## What was extended, and how

Zero existing files were modified beyond three single-purpose,
mechanically necessary wiring edits — verified with `diff` against the
original project (see below) — `app/models/__init__.py` (register the
new model), `app/api/v1/api.py` (register the new router), and
`seed.py` (register the new `rent_vouchers` permission module). No
existing table, model, service method, or route was changed.

### New database table: `rent_vouchers`

One new table. Does **not** touch `transactions`, `tenants`,
`properties`, or `rental_payment_installments` — see
`app/models/rent_voucher.py` for the full design note.

| Column | Notes |
|---|---|
| `id`, `uuid`, `status`, `created_at`, `updated_at`, `deleted_at`, `created_by`, `updated_by` | Standard audit columns |
| `voucher_number` | `RV-000001`, sequential, unique |
| `transaction_id` | FK → `transactions.id` — "linked directly with the rental payment transaction," per spec |
| `copy_type` | `tenant` \| `company` |
| `rental_month` | The selected rental month (spec: **month only** — no from/to date range) |
| `barcode_value` | Unique. `{voucher_number}-{transaction_number}` |
| `print_count`, `printed_at` | Print/reprint history — identical pattern to `Invoice.print_count`/`printed_at` and `RentalPaymentInstallment.print_count`/`printed_at` |
| `notes` | Free text |

`UNIQUE(transaction_id, copy_type)` — makes generating a duplicate
Tenant/Company copy for the same transaction impossible at the database
level, on top of the service layer's own idempotency check.

Every other field the voucher needs (tenant name/ID/phone, building,
unit, address, amount, payment method) is a **read-only `@property`**
resolved through `transaction_id`, never a stored/duplicated column —
same pattern as `RentCycleRecord` (Phase 14). "Amount in Words" (both
languages) is computed on read via the existing, unmodified
`app/core/number_to_words.amount_to_words()` — the exact function
already used by the Rental Receipt Module, so voucher and receipt
wording can never drift apart.

Migration: `app/alembic/versions/0019_rent_voucher_module.py`.

### API endpoints (`/api/v1/rent-vouchers`)

| Method & path | Permission | Notes |
|---|---|---|
| `POST /rent-vouchers/generate` | `rent_vouchers.create` | Body: `{transaction_ids: [...], rental_month: date}`. Generates a Tenant Copy + Company Copy pair per transaction; safe/idempotent if some pairs already exist |
| `GET /rent-vouchers` | `rent_vouchers.view` | Paginated; filter by `rental_month`, `copy_type`, `transaction_id` |
| `GET /rent-vouchers/{id}` | `rent_vouchers.view` | |
| `GET /rent-vouchers/barcode/{value}` | `rent_vouchers.view` | Barcode-scan lookup |
| `GET /rent-vouchers/{id}/print-data` | `rent_vouchers.view` | The bilingual print-ready DTO for one voucher |
| `POST /rent-vouchers/print-data/bulk` | `rent_vouchers.view` | Body: `{voucher_ids: [...]}` — up to 4 for one A4 sheet |
| `POST /rent-vouchers/{id}/record-print` | `rent_vouchers.edit` | Called right before the browser print dialog |

Permission codes (`rent_vouchers.view/create/edit`) follow the same
`module.action` catalog every other module already uses, added to
`seed.py`'s `MODULES` list and to the Branch Manager / Staff system
roles.

### Business rules enforced

- A voucher can only be generated for a transaction whose
  `transaction_type == "tenant_payment"` — 400 otherwise. This module
  never creates, edits, or reverses a `Transaction`.
- Generating for a transaction that already has a Tenant/Company copy
  is a safe no-op for that pair (reuses the existing rows), not an
  error — matches how `FinancialService.generate_bulk_invoices` treats
  an already-billed period.
- No "Rental Period" (from/to date) field exists anywhere — only
  `rental_month`, per spec.

## Testing

`backend/tests/test_rent_voucher_module.py` — pair generation,
idempotency, rejection of non-tenant-payment transactions, multi-
transaction batch generation, the bilingual print DTO (including the
K-Net/Cash payment-method mapping and the amount-in-words match to the
spec's own worked example — "One Thousand Two Hundred Fifty Kuwaiti
Dinars Only" for 1,250 KWD), barcode lookup, print/reprint tracking, the
full API workflow, and permission enforcement.

## Verified backward compatibility

```
diff -rq <original>/app/services   <modified>/app/services    # empty
diff -rq <original>/app/models     <modified>/app/models      # empty, excl. 2 new files
diff -rq <original>/app/repositories ...                      # empty, excl. 1 new file
diff -rq <original>/app/schemas    ...                        # empty, excl. 1 new file
diff -rq <original>/app/api/v1/routers ...                    # empty, excl. 1 new file
```

All 164 backend `.py` files (source + tests, including this phase's
additions) compile cleanly with no syntax errors.

## Frontend implementation (added after initial delivery)

The A4/four-per-page print template described as future frontend work
below was subsequently built, following this codebase's existing print
page conventions (`RentalReceiptPrintPage.tsx`, `InvoicePrintPage.tsx`)
exactly:

- **`frontend/src/pages/RentVoucherPrintPage.tsx`** — the actual
  printable page. A4 portrait, four full-width horizontal vouchers,
  each with a real professional border. **Letterhead-safe margins are
  reserved and blank** (default 20mm top / 15mm bottom, overridable via
  `?marginTop=`/`?marginBottom=`, shown as a faint on-screen-only guide
  that disappears on the actual printed page) — the four voucher bands
  split only the *remaining* height, never the full 297mm, so nothing
  overlaps a physical letterhead. Every bilingual label is stacked
  English-then-Arabic on two lines, matching the spec's own example
  layout literally (one deliberate, documented exception: the six
  tenant/property detail rows use a compact single-line "EN · AR"
  layout instead, since stacking all six wouldn't fit in a quarter-A4
  voucher once the letterhead margin is reserved). Barcode rendering
  uses `JsBarcode`, loaded from a CDN at runtime — no new frontend
  *or* backend dependency was added for it. Optional watermark support
  (`?watermark=TEXT`) was added per the spec's "optional" design line.
  "Export PDF" and "Print directly on A4 letterhead" are the same
  browser print dialog (its "Save as PDF" destination *is* the export
  path) — documented on-screen rather than pretending these are two
  separate pipelines, since no server-side PDF generation exists (see
  the conflict section above for why that's the right call).
- **`frontend/src/pages/RentVouchersPage.tsx`** — the missing "SYSTEM
  FUNCTIONS" UI: select apartment (filter), select rental month, select
  payment transaction(s), Generate Vouchers, and a list of already-
  generated vouchers grouped back into Tenant/Company pairs (by
  `transaction_id`) so "Print Selected" always hands the print page a
  correctly ordered `[tenant, company, tenant, company]` id list — the
  spec's required page ordering is enforced structurally, not left to
  the user to get right.
- Reachable from `/rent-vouchers`, linked from the Rental Contracts page
  next to the existing Rental Receipts link (same discoverability
  pattern), permission-gated by the existing `rent_vouchers.view`/
  `.create` codes.

Five frontend files touched in total, four of them purely additive
(two new pages, one new route registration, one new link button); the
fifth (`types/index.ts`) gained two new interfaces
(`RentVoucher`, `RentVoucherPrintData`) and nothing else changed.

## Explicitly out of scope

- **A true server-rendered PDF path** — see the conflict section above;
  would require adding `arabic-reshaper` + `python-bidi` to
  `requirements.txt` first.
- **QR code** — explicitly marked "future versions" in the spec (unlike
  the watermark, which was implemented — see above); the data contract
  doesn't preclude adding one later (it would reuse
  `app/core/qr_code.py` unchanged, the same way the Rent Billing
  Engine's invoice QR code already does).
