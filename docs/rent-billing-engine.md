# Rent Billing Engine

## Pre-implementation analysis (required before any code was written)

The spec required inspecting the existing system first and never
duplicating what already exists. Two findings changed the design
substantially from a literal reading of the spec:

1. **"Rent Invoice" already exists** — the `Invoice` model (issue_date/
   due_date/status, a working payment-recording flow) already *is* a
   billing document distinct from a payment receipt. Extended, not
   duplicated.
2. **"Payment Receipt" already exists** — the `Receipt` model is
   already auto-issued only after a payment transaction, by
   `FinancialService.create_transaction()`. Extended, not duplicated.
3. **Billing cycles already existed** at the contract level
   (`RentalPaymentFrequency`: monthly/quarterly/semi_annual/annual/
   one_time/custom) — nothing to build there, just to make the
   generation engine actually respect each contract's own value.
4. **A separate, pre-existing "Rental Receipt Module"** (built in an
   earlier phase, `RentalPaymentInstallment`-based, `RR-` numbering)
   covers a simpler print-before-payment workflow. It is **deliberately
   left completely untouched** — this Rent Billing Engine is a richer,
   `Invoice`-based system for the same broad problem, not a replacement.
   Both are documented and both work; which one a given deployment uses
   is an operational choice, not something this codebase forces.

## Explicit scope decisions

- **Invoice numbering format**: the spec's example (`RR-2026-000001`)
  implies a year-scoped sequence. The existing `INV-000001` format
  (global sequence, not year-scoped) is already live on real invoice
  data from earlier phases. Changing the format would break backward
  compatibility, which the spec itself mandates preserving. Kept as-is.
- **Status lifecycle**: added `PARTIALLY_PAID` and `VOID` as genuinely
  new, mutually-exclusive statuses. Deliberately did **not** add
  separate `ISSUED`/`PRINTED`/`DELIVERED` statuses — those aren't
  mutually exclusive with the rest of the lifecycle (an invoice that's
  been delivered hasn't stopped being "sent"). Modeled instead as
  independent timestamps (`printed_at`/`print_count`, `delivered_at`)
  that can coexist with any status. `SENT` is kept as the existing name
  for what the spec calls "Issued," for backward compatibility.
- **Receipt Designer**: the spec asks for a full visual designer
  (drag-and-drop logo position/size, colors, fonts, watermark, margins,
  "without modifying code"). This was **not built** — it's a
  substantial standalone feature disproportionate to this pass. What
  exists instead: the printable template's colors/layout are controlled
  by code (`InvoicePrintPage.tsx`), and company info (name, logo URL,
  address, phone, email, website) already flows from the existing
  `CompanyProfile` settings into every invoice's snapshot. A true
  visual designer is a reasonable follow-up, not a silent omission.
- **Automatic monthly generation**: manually triggered
  (`POST /financial/invoices/bulk-generate`), same documented decision
  as the Rental Receipt Module and Export Scheduling before it — no
  scheduler (APScheduler/Celery) exists anywhere in this codebase.
- **QR code**: contains only a verification URL
  (`{PUBLIC_APP_URL}/verify/{qr_token}`) pointing at a public, minimal
  endpoint — never the invoice content itself, per spec ("nothing
  sensitive"). `qr_token` is a random UUID, not the sequential
  `invoice_number` or numeric id, so the QR code can't be used to
  enumerate other invoices.

## Data model

`Invoice` (existing table, extended — migration `0015`):

| Column | Notes |
|---|---|
| `billing_cycle` | Snapshot of the contract's `payment_frequency` at generation time. |
| `billing_period_start` / `billing_period_end` | The period this invoice bills for; `_end` is computed per-cycle (see below), never hardcoded to a month. |
| `snapshot` (JSON) | Tenant name/address/civil ID/phone, property/building/unit, contract number, rent/discount/tax breakdown, and company info — all frozen at generation time. Printable documents render from this, never from live data. |
| `amount_paid` | Accumulates across possibly multiple partial payments. |
| `void_reason` / `voided_at` | Set by the `/void` action (reason mandatory). |
| `printed_at` / `print_count` | Bumped by `/print`, never by `/print-data` (the no-side-effect preview). |
| `delivered_at` | Set by `/deliver`. |
| `qr_token` | Unique, opaque, random — the verification link's identifier. |

`Receipt` (existing table, extended): `invoice_id` (links a payment's
auto-issued receipt back to the invoice it settled), `printed_at`,
`print_count`.

## Billing cycle computation

`FinancialService._compute_period_end(start, billing_cycle)` is the one
place a start date + a cycle becomes an actual period end:
monthly → +1 month, quarterly → +3 months, semi_annual → +6 months,
annual → +1 year, custom → a configurable day count, one_time → same
day. A single bulk-generation run correctly produces a ~30-day invoice
for a monthly lease and a ~90-day invoice for a quarterly one in the
same call, because each contract's own `payment_frequency` drives its
own invoice's period — nothing here is hardcoded to monthly.

## API reference

All under the existing `/financial` router.

| Endpoint | Permission | Purpose |
|---|---|---|
| `POST /financial/invoices/bulk-generate` | `financial.create` | Body: `{billing_period_start, property_ids?}`. Generates draft invoices for every active contract (optionally scoped to a building/property/owner's unit ids) that doesn't already have one for that exact period. Idempotent. |
| `POST /financial/invoices/bulk-approve` | `financial.edit` | Draft → Sent for a list of invoice ids. |
| `POST /financial/invoices/bulk-print` | `financial.view` | Fetches printable data for a list of ids and records the print/reprint for each — backs Print Selected / Entire Building / Entire Property / Entire Owner / Entire Month, which all reduce to "a list of ids" via search below. |
| `GET /financial/invoices/search` | `financial.view` | Filters: invoice_number, tenant_id, property_id, owner_id, rental_contract_id, phone, civil_id, invoice_status, date_from/to. |
| `GET /financial/invoices/verify/{qr_token}` | none (public) | The QR code's target. Returns only invoice_number/issue_date/status — no amounts, no tenant data. |
| `POST /financial/invoices/{id}/void` | `financial.edit` | Reason **required**. Distinct from `/cancel`. |
| `POST /financial/invoices/{id}/cancel` | `financial.edit` | Pre-existing endpoint; reason now optional (kept backward compatible — it never required one before). |
| `POST /financial/invoices/{id}/print` | `financial.view` | Increments print_count, returns the printable DTO. |
| `GET /financial/invoices/{id}/print-data` | `financial.view` | Same DTO, no side effect — for "Print Preview." |
| `POST /financial/invoices/{id}/deliver` | `financial.edit` | Sets `delivered_at`. |
| `POST /financial/invoices/{id}/record-payment` | `financial.edit` | Extended with optional `amount` — omit for full payment (byte-identical to the pre-existing behavior), or pass a partial amount. |

New reports (`/reports/invoices/register`, `/payment-register`,
`/overdue`) and dashboard widgets (invoices generated/paid this month,
due today, overdue amount, collection rate, top debtors) reuse the
existing Reports and Financial Dashboard endpoints rather than adding
new ones — "Building/Owner Collection Report" and "Tenant Statement"
reuse the pre-existing `/reports/collections` and `/reports/tenants`,
which already support the needed filtering.

## Printing

Browser-rendered (same architecture as the Rental Receipt Module, for
the same reason: reuses this app's existing print CSS rather than
adding a second rendering path). Landscape, half/quarter/full A4,
letterhead-safe (no logo/header printed — the physical paper already
has it), tenant copy (excludes civil ID/phone/status/internal notes)
vs. company copy (includes them plus signature/collector fields).

## Testing

`backend/tests/test_rent_billing_engine.py` — 30 tests: bulk generation
(including idempotency and that a quarterly contract's period is ~90
days, not 30), snapshot immutability (an invoice's printed data is
unaffected by later tenant/property edits), the void-requires-reason
vs. cancel-stays-optional distinction, partial payment accumulation and
over-payment rejection, receipt-invoice linking, search, QR
verification's public/minimal contract, the three new reports, the
extended dashboard, and explicit regression tests confirming the
pre-existing Invoice CRUD/payment flow and the separate Rental Receipt
Module are both unaffected.

## Known limitations

- No visual Receipt Designer (see Scope Decisions above).
- QR codes and snapshots are only generated by the bulk-generation path
  (`POST /invoices/bulk-generate`); invoices created via the older,
  still-functional single `POST /invoices` endpoint won't have a QR
  code or snapshot, since that endpoint predates this phase and wasn't
  changed. New sample seed data demonstrates the new path
  (`INV-000002`) alongside the original simple one (`INV-000001`).
- Same third-party-dependency caveat as the rest of this project's
  recent phases: `qrcode`/`Pillow` were added and written against their
  documented public API, but this sandbox has no package-manager
  network access, so they were never executed here. Run the test suite
  in a real environment before deploying.
