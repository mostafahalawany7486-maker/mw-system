# Property Management System — Phase 1: Project Foundation

Cloud-native PMS built for a company that leases properties from owners and
subleases them to tenants. This phase delivers the platform foundation:
authentication, RBAC, organization setup, and cross-cutting system
infrastructure (attachments, notes, activity log, audit log, notifications).

Stack: **FastAPI + PostgreSQL** (backend) · **React + TypeScript + Tailwind**
(frontend) · **Docker** · designed for **Azure** deployment.

## Quick Start (local, via Docker)

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker-compose up --build
```

This will:
1. Start PostgreSQL
2. Run Alembic migrations (`alembic upgrade head`)
3. Run `seed.py` (permissions, roles, admin user, lookup data)
4. Start the FastAPI backend on **http://localhost:8000**
5. Start the React frontend on **http://localhost:5173**

API docs (Swagger): **http://localhost:8000/api/v1/docs**

## Default login

As of the [Fresh Start / demo-data removal](#fresh-start-no-demo-business-data)
change below, `seed.py` only creates one login — the Administrator:

| Role | Email | Password |
|---|---|---|
| Administrator | value of `FIRST_ADMIN_EMAIL` in `.env` (defaults to `admin@pms-demo.com`) | value of `FIRST_ADMIN_PASSWORD` in `.env` (defaults to `Admin@12345`) |

**Change these immediately after first login in any non-local environment.**

The Branch Manager (`maria.manager@pms-demo.com`) and Staff
(`sam.staff@pms-demo.com`) demo logins that earlier versions of this
README described are no longer seeded by default — see below. Create
real user accounts for your team from **Users** in the app instead (or
restore the old demo dataset if you specifically want those two demo
logins back).

## Fresh Start (no demo business data)

`seed.py` used to also create ~2 sample Owners, 3 Tenants, 6 Properties,
sample Lease/Rental Contracts, Financial transactions, Maintenance
data (contractors/technicians/requests/contracts), Accounting data
(chart of accounts, journal entries), Report Schedules, and two extra
demo logins (Branch Manager / Staff) — useful for a first look at the
app, but actively in the way once a real company starts using a
deployment: real Owners/Tenants/balances have to be entered around a
pile of fictional ones.

`seed.py` now seeds **only foundational/setup data** — the permission
catalog and system roles, Countries/Cities, Currencies, the Company
Profile placeholder, the Head Office branch, System Settings, the
Amenities lookup catalog (kept because it's a reusable picklist for
the Properties module, not fictional business data — the same reason
Countries/Currencies are kept), and the first Administrator account.
Nothing about how migrations, permissions, or any endpoint works
changed — this only trims what a fresh `python seed.py` inserts.

**Company Profile and the Head Office branch are also genuinely blank
now**, not just trimmed — they used to be pre-filled with a fake
example company ("PMS Leasing Company LLC", a placeholder US address,
`info@pms-demo.com`, New York/United States as the default location).
That looked plausible enough to accidentally ship on a real invoice or
voucher if nobody noticed and changed it. `CompanyProfile.legal_name`
is the one field that can't be left empty at the database level, so it
seeds as the unmistakable placeholder `"My Company"`; every other
field (email, phone, address, city, country, base currency, logo) is
left unset. **Set your real company details from Company Profile as
one of the first things you do after a fresh install** — nothing else
in the app requires this to function, but invoices/vouchers/reports
will otherwise print with the placeholder name until you do.

**Operationally important:** this also means a fresh install now has
**zero Financial Accounts and an empty Chart of Accounts** (both used
to come from the removed Sample Financial/Accounting Data). Payments,
Invoices, Rent Vouchers, and the Collect Rent screen all require at
least one Financial Account to exist first — create one from
**Financial → Add Account** before using any of them. If you want
proper double-entry accounting (not required, but recommended before
going live), also set up your Chart of Accounts from **Accounting**
before recording real transactions.

**Nothing is deleted automatically from an existing database** — this
only changes what a *fresh* `python seed.py` run creates going forward.
If you already ran the old seed script against a database and want to
clear out its fictional Owners/Tenants/Properties/transactions/etc.
before entering your own company's data, either:
- drop and recreate the database, then run `alembic upgrade head &&
  python seed.py` again (cleanest, since it also re-applies migrations
  from scratch), or
- delete the specific fictional records by hand from the UI/API (Owners,
  Tenants, Properties, Leases, Rental Contracts, Financial Accounts —
  deleting a Property/Owner/Tenant that still has linked
  leases/contracts/transactions will be blocked by the same
  referential-integrity checks that protect real data, so work
  top-down: contracts and transactions first, then properties/owners/
  tenants).

The old script, with all of the above sample data and the two demo
logins, is kept at
[`backend/seed_with_demo_data.py.bak`](backend/seed_with_demo_data.py.bak)
for anyone who wants that richer dataset back — for a sales demo or a
QA/staging environment, for example. Copy it back over `seed.py` (or
run `python seed_with_demo_data.py.bak` directly) to use it.

## Manual setup (without Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # then edit DATABASE_URL to point at your Postgres instance
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Running tests
```bash
cd backend
pytest
```

## Pushing to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Nothing sensitive gets committed: `backend/.env` and `frontend/.env` are
git-ignored (only the placeholder `.env.example` files are tracked), and
`backend/storage/` (local file uploads) is also ignored. Double-check
`git status` before your first commit if you're unsure.

## Deploying to Render

This repo includes a [`render.yaml`](render.yaml) Blueprint that provisions
everything in one step: a managed Postgres database, the FastAPI backend
(built from `backend/Dockerfile`, the same image used for local Docker
dev), and the React frontend as a static site.

1. Push this repo to GitHub (above) if you haven't already.
2. In the [Render Dashboard](https://dashboard.render.com), click **New +
   → Blueprint**, and connect this repository. Render detects
   `render.yaml` automatically.
3. Render will prompt for one value it can't generate itself:
   `FIRST_ADMIN_PASSWORD` (the initial admin login for `python seed.py`,
   which runs automatically on deploy). **Pick a real password here — do
   not reuse the demo password from `backend/.env.example`.**
   `SECRET_KEY` is generated for you automatically.
4. Click **Deploy Blueprint**. Render provisions the database first, then
   builds and deploys both services. First boot runs
   `alembic upgrade head && python seed.py` before starting the API (see
   `render.yaml` for exactly how).
5. **After the first deploy, open both services in the dashboard and
   check their actual URLs.** Render normally assigns
   `https://pms-backend.onrender.com` / `https://pms-frontend.onrender.com`
   (the names declared in `render.yaml`), but appends a random suffix
   instead if either exact name is already taken by someone else on the
   platform. If that happened, update these three environment variables
   to match the real URLs, then redeploy:
   - `pms-backend`'s `BACKEND_CORS_ORIGINS` and `PUBLIC_APP_URL` → the
     real frontend URL
   - `pms-frontend`'s `VITE_API_BASE_URL` → the real backend URL, with
     `/api/v1` appended

**Two honest limitations of the default (free-tier) setup, not bugs:**
- Free web services spin down after 15 minutes of inactivity and take
  ~30-60s to wake up on the next request.
- Free-tier disk is ephemeral — `STORAGE_BACKEND=local` (the default)
  means uploaded attachments do **not** survive a redeploy or restart.
  For real attachment persistence, either switch `STORAGE_BACKEND` to
  `azure_blob` (already supported — see `backend/.env.example` for the
  two extra variables it needs) or add a
  [Render persistent disk](https://render.com/docs/disks) on a paid plan.

Prefer to configure services by hand instead of using the Blueprint?
`render.yaml` is also just documentation of exactly which build/start
commands and environment variables each service needs — read through it
and set them up manually in the dashboard the same way.

An Azure deployment path already exists too (Terraform in `infra/`, full
walkthrough in `docs/deployment-azure.md`) — Render is a second,
simpler option, not a replacement.

## Project structure

```
pms/
├── backend/
│   ├── app/
│   │   ├── core/            # config, database, security
│   │   ├── models/          # SQLAlchemy models (all inherit BaseModel)
│   │   ├── schemas/         # Pydantic DTOs
│   │   ├── repositories/    # Repository pattern (data access)
│   │   ├── services/        # Business logic / service layer
│   │   ├── api/v1/routers/  # FastAPI route handlers
│   │   └── alembic/         # DB migrations
│   ├── tests/                # pytest suite
│   ├── seed.py                # seed data script
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/            # route-level pages
│   │   ├── components/       # reusable UI + layout
│   │   ├── context/          # Auth + Theme context
│   │   ├── api/               # axios client
│   │   └── types/             # shared TS types
│   └── Dockerfile
├── docker-compose.yml
└── docs/                      # testing, deployment, security checklists (this phase's deliverables)
```

See `/docs` for the full Phase 1 testing checklist, UAT script, permissions
matrix, and deployment guide. Phase 2 (Property Owners) adds
`docs/phase2-testing-checklist.md` and `docs/phase2-uat-script.md`.

## Phase 2: Property Owners

Adds the first business entity: Property Owners (individual or company),
each with addresses, bank accounts, additional contacts, and legal
documents (with expiry tracking) — plus search, filters, and a dedicated
owner dashboard. This is the first link in the business chain: **Owner →
Lease Agreement → Company → Sublease → Tenant** (later phases build the
rest of that chain on top of this).

New migration: `0002_property_owners.py`. New permission module: `owners`
(view/create/edit/delete). Run `python seed.py` again after migrating to
load 2 sample owners.

## Phase 3: Lease Agreements (Owner → Company)

Adds the contract layer: Lease Agreements between the company and a
Property Owner, with contract numbers, start/end dates, a full
draft→active→terminated/renewed status machine, payment schedule
generation (monthly/quarterly/semi-annual/annual/one-time/custom),
security deposit tracking, attachments, activity history, and renewal
reminders.

New migration: `0003_lease_agreements.py`. New permission module: `leases`
(view/create/edit/delete). New dependency: `python-dateutil` (month-based
date math for payment schedules).

**Renewal reminders are on-demand, not automatic yet** — no background
scheduler exists in this stack. Click "Check Renewals" in the UI (or
`POST /leases/maintenance/run`) to trigger the sweep. See
`docs/phase3-renewal-reminders.md` for wiring this to a real scheduler in
production.

## Phase 4: Property Management

Adds the physical asset layer: Properties covering all 10 requested kinds
(Building, Villa, Apartment, Commercial Unit, Warehouse, Shop, Office,
Land, Parking, Storage), each with a system-generated property code,
optional internal code, owner linkage, computed current-lease linkage,
location + GPS, an image gallery with cover-photo selection, structured
documents with expiry tracking, a shared amenities catalog, availability
status, and a Building→Units hierarchy for properties that live inside a
larger building.

New migration: `0004_property_management.py` — adds `properties`,
`amenities`, `property_amenities`, `property_images`, `property_documents`,
plus an additive nullable `property_id` column on `lease_agreements` (so
Phase 3 leases can now formally reference a Phase 4 property; existing
leases are unaffected). New permission module: `properties`
(view/create/edit/delete).

## Phase 5: Unit Management

Extends Property (Phase 4) with everything needed to manage individual
units within a building: a first-class **Floor** entity (so floors can be
listed/managed, not just a free-text label), **Unit Numbers**, **Rent
Price** (the listed/asking price, intentionally kept separate from a
lease's actual signed `rent_amount` from Phase 3), **Electricity/Water
Meter** numbers, and the ability to assign an existing **Parking** or
**Storage** property to a unit (validated to actually be that type).
**Availability**, **Images**, and **Documents** are unchanged — they were
already built generically in Phase 4 and apply to units the same as any
other property.

New migration: `0005_unit_management.py` — adds a `floors` table and 7
nullable columns on `properties` (fully additive; no Phase 4 data is
affected). No new permission module — floors and unit fields are managed
under the existing `properties.*` permissions, the same pattern used for
Owner sub-resources under `owners.*` in Phase 2.

### Building Management extension (post-Phase 11)

A `Property` with `property_type="building"` already **is** the Building
entity — Phases 4/5 gave it the full hierarchy (`Floor`s, and child
`Property` rows as Units via `parent_property_id`), and Phases 7/9 gave
it Leases and Maintenance Requests via each unit's `property_id`. No new
entity was created for "Building Management"; instead, the existing
building detail page was extended with a live summary (floor count, unit
count, occupied/vacant units, active/expired leases, tenant count, open
maintenance requests) and three new tabs — **Leases**, **Tenants**, and
**Maintenance** — that aggregate across the building *and* everything
nested under it.

This required no migration. Four new read-only endpoints were added
under the existing `properties` router, all reusing the Rental
Contracts/Tenants/Maintenance modules' own list schemas (no duplicated
DTOs) and gated by the existing `properties.view` permission (no new
permission module):
- `GET /properties/{building_id}/building-summary`
- `GET /properties/{building_id}/leases` (optional `?contract_status=`)
- `GET /properties/{building_id}/tenants`
- `GET /properties/{building_id}/maintenance-requests`

Each resolves "the building and its units" as `[building_id] + [unit ids
where parent_property_id == building_id]`, then filters the relevant
table's own `property_id` column against that set — the same tables and
relationships the Rentals/Tenants/Maintenance modules already use, just
queried from the building's point of view instead of a single unit's.

## Phase 6: Tenant Management

Adds the Tenant entity — the company SUBLEASES properties TO these
tenants (see business model: Owner → Lease Agreement → Company → Sublease
→ Tenant). Mirrors Phase 2's Owner module almost exactly (individual vs.
company, contacts, documents), plus two new concepts: a **Blacklist**
flag with a required reason and full audit trail, and a **Tenant Rating**
system (1-5 stars, multiple entries over time, averaged at read time).
Also adds a dedicated **Emergency Contact** sub-resource, distinct from
general Contacts, since emergency contacts have a mandatory phone number
and a different real-world purpose.

New migration: `0006_tenant_management.py` — adds `tenants`,
`tenant_contacts`, `tenant_emergency_contacts`, `tenant_documents`,
`tenant_ratings`. New permission module: `tenants`
(view/create/edit/delete) — blacklist and rating actions reuse
`tenants.edit` rather than adding new granular permissions, consistent
with how lease status transitions (Phase 3) reused `leases.edit`.

The Sublease Agreement linking Tenant to Property (mirroring Phase 3's
Lease Agreement between Company and Owner) is a natural next phase.

## Phase 7: Rental Contracts (Company → Tenant)

The final link in the business model chain: Owner → Lease Agreement →
Company → **Rental Contract** → Tenant. Structurally mirrors Lease
Agreement (Phase 3) closely — same status machine (draft → active →
expired/terminated/renewed), same renewal-creates-a-new-row pattern, same
on-demand maintenance sweep — with three new financial concepts layered
on top: **Discounts** (percentage or fixed, applied per installment),
**Taxes** (a rate applied to the post-discount amount), and **Late Fees**
(percentage or fixed, with a configurable grace period, assessed
idempotently by the maintenance sweep so repeated runs never double-charge).

Activating a contract now also marks its property as "Leased"; terminating
it frees the property back to "Available" — closing the loop between
Rental Contracts and the Property/Unit availability tracking built in
Phases 4–5. Creating a contract for a blacklisted tenant (Phase 6) is
allowed, not blocked — the system surfaces a clear warning in both the API
response and the UI, leaving the call to staff rather than hard-enforcing
it.

New migration: `0007_rental_contracts.py` — adds `rental_contracts` and
`rental_payment_installments`. New permission module: `rentals`
(view/create/edit/delete) — all status transitions (activate/terminate/
renew) and payment schedule management reuse `rentals.edit`.

## Phase 8: Financial Management

Covers Tenant Payments, Owner Payments, Receipts, Invoices, Expenses,
Income, Deposits, Refunds, Cash & Bank accounts, Transfers, and
Outstanding Balance. Rather than building seven near-identical tables for
each payment/expense/income concept, this phase uses a single unified
ledger table (`Transaction`) with a `transaction_type` discriminator —
the same pattern established for Owner (Phase 2), Property (Phase 4), and
Tenant (Phase 6). Transfers are the one exception: each transfer creates
**two** linked Transaction rows (`transfer_out` + `transfer_in`) rather
than one row referencing two accounts, which keeps per-account balance
math a simple sum with no special-casing.

Tenant Payments and Owner Payments optionally link back to a specific
Rental Payment Installment (Phase 7) or Lease Payment Installment
(Phase 3); recording a linked payment here automatically marks that
installment paid, so there's one source of truth instead of two
disconnected ledgers. Receipts are auto-issued (not manually created) for
every Tenant and Owner Payment. Account balances and Outstanding Balance
are never stored — both are computed live from the transaction/installment
history on every read, so they can never drift out of sync.

New migration: `0008_financial_management.py` — adds `financial_accounts`,
`transactions`, `receipts`, `invoices`. New permission module: `financial`
(view/create/edit/delete) — Transfers, Invoice send/cancel, and Record
Payment all reuse `financial.create`/`financial.edit`.

## Phase 9: Maintenance

Covers Maintenance Requests, Priority, Contractors, Technicians,
Materials, Labor Cost, Before/After Photos, Status, and History.
`MaintenanceRequest` follows the same explicit-action status-machine
pattern established in Phases 3/7 (`assign`/`start`/`hold`/`resume`/
`complete`/`cancel` endpoints rather than a generic "set status" call),
which produces clearer audit history and lets the UI show only the
buttons that are actually valid for the current state.

Materials and Labor Cost are per-request line items rather than a single
guessed total — "actual cost" is always the live sum of what was actually
logged, so it can never drift. Before/After Photos get first-class fields
(a `photo_type` discriminator) rather than being folded into the generic
Phase 1 Attachment table, since "before vs. after" is a specific,
structured concept worth its own column. Contractors and Technicians are
a lightweight directory — a Technician may optionally belong to a
Contractor (contracted labor) or have no `contractor_id` (in-house staff).

New migration: `0009_maintenance.py` — adds `contractors`, `technicians`,
`maintenance_requests`, `maintenance_materials`, `maintenance_labor_costs`,
`maintenance_photos`. New permission module: `maintenance`
(view/create/edit/delete) — all status transitions and materials/labor/
photo management reuse `maintenance.edit`. Staff additionally gets
`maintenance.create` (but not `.edit`) so front-line staff can report
issues without managing the full workflow.

## Phase 10: Accounting

A proper double-entry general ledger sitting underneath the operational
Financial Management module (Phase 8): Chart of Accounts, Journal
Entries, General Ledger, Trial Balance, Balance Sheet, Income Statement,
Cash Flow, Cost Centers, VAT, and Automatic Posting.

Chart of Accounts is a self-referential tree — header/summary accounts
for grouping, leaf accounts (`allow_posting=true`) for actual entries.
Journal Entry follows a strict `draft → posted → reversed` lifecycle: a
posted entry can never be edited or deleted, only reversed (a brand-new
offsetting entry), which keeps a complete audit trail the way real
accounting systems do. Every one of the reports — General Ledger, Trial
Balance, Balance Sheet, Income Statement, Cash Flow, and the VAT report —
is computed live from posted journal entry lines on every request; none
of them are stored tables, so they can never drift out of sync with the
ledger.

**Automatic Posting** is the key integration point with Phase 8: a
`PostingRule` maps a Financial transaction (by type, optionally narrowed
by category) to a GL "offset" account, and a new nullable
`FinancialAccount.gl_account_id` link (added additively — no existing
Phase 8 data touched) tells the system which GL account represents that
Cash/Bank account. When a transaction is created via the API, a hook in
`FinancialService` automatically posts a balanced journal entry — silently
skipping (never blocking the underlying transaction) if no rule or GL
link exists yet. Transfers post exactly one journal entry per pair, not
two. Deleting a transaction with a posted journal entry attached is
blocked until that entry is reversed, protecting ledger integrity.

VAT is handled as a single "VAT Control" account per rate, netting
payable and receivable together — a deliberate simplification appropriate
for this scale of operation, documented in `docs/phase10-validation-rules.md`.
The seeded default posting rules are intentionally VAT-free, since Phase
8's historical transaction amounts were recorded without a tax-inclusive
assumption.

New migration: `0010_accounting.py` — adds `chart_of_accounts`,
`cost_centers`, `vat_rates`, `posting_rules`, `journal_entries`,
`journal_entry_lines`, plus an additive `gl_account_id` column on
`financial_accounts`. New permission module: `accounting`
(view/create/edit/delete) — deliberately more restricted than other
modules: Staff has no accounting access at all, and Branch Manager gets
`accounting.view` only, since ledger access is typically limited to
accounting staff and administrators.

## Phase 11: Reports

Financial Reports, Tenant Reports, Owner Reports, Property Reports,
Vacancy Reports, Occupancy Reports, Income Reports, Expense Reports,
Profit Reports, and Dashboard Analytics — **no new migration**, since
every report is computed live from Phases 1–10's existing data. This is
deliberately distinct from Phase 10's accounting-grade financial
statements (which require posted journal entries): these are fast,
operational business reports computed directly from source transactional
data, so they're useful even before the general ledger is fully
configured.

A few notable design decisions, documented in full in
`docs/phase11-validation-rules.md`:
- Property attribution for income/expense reports resolves through
  `Transaction.property_id` first, falling back to the linked rental
  contract's property when not set directly.
- `property_type == "building"` rows are excluded from all vacancy/
  occupancy math, since buildings are parent containers for their units
  (Phase 4/5 design), not directly leasable space themselves.
- The occupancy trend is an honest approximation (current property counts
  against historical contract date ranges, since historical property
  counts aren't tracked) rather than a false precision.
- Expense reports show Financial `expense` transactions and Phase 9
  maintenance costs as two separate figures rather than summing them,
  since the system can't know whether a given maintenance job's cost was
  also separately recorded as a Financial transaction — summing by
  default would risk silently double-counting.

New permission module: `reports` (view/create/edit/delete generated for
schema consistency, but only `.view` is ever checked — every endpoint is
a read-only GET). Both Branch Manager and Staff get `reports.view`,
consistent with their existing `financial.view` access from Phase 8.

### Property Profit Center extension (post-Phase 11)

Every `Property` is now a fully-linked financial profit center — no new
entity was created; instead, every financial record type that previously
lacked a direct property attribution was extended additively:

- **Transaction** already had `property_id` (Phase 8/11) but no
  relationship or `property_title` helper — both added, and creating a
  transaction now **auto-fills** `property_id` from its
  `rental_contract_id` or `lease_agreement_id` when not given directly,
  so new transactions are attributed automatically rather than requiring
  the caller to resolve it themselves.
- **Invoice** gained a nullable `property_id` column, with the same
  auto-fill behavior from `rental_contract_id`.
- **JournalEntryLine** gained a nullable `property_id` column,
  independent of (and more direct than) the existing `cost_center_id` →
  `CostCenter.property_id` indirection — automatic posting now tags
  every generated line with the source transaction's property.
- **Receipt** and **MaintenanceRequest** already resolved to a property
  (via their linked Transaction / a required direct `property_id`
  respectively) — no changes needed there.
- **"Cash Transactions" / "Bank Transactions"** were never separate
  entities — they're `Transaction` rows where the linked
  `FinancialAccount.account_type` is `cash` or `bank`; property
  attribution on `Transaction` covers both automatically.

New migration: `0011_property_profit_center.py` — two additive nullable
FK columns (`invoices.property_id`, `journal_entry_lines.property_id`)
plus an index on the pre-existing but previously-unindexed
`transactions.property_id`. No existing data is touched.

**Seven new reports**, reusing rather than duplicating the existing
report services:
- `GET /properties/{id}/reports/profit-loss` — Property P&L (Phase 11's `ReportsService`, `reports.view`)
- `GET /properties/{id}/reports/expense` — Property Expense Report (the *same* `expense_report()` method Phase 11's portfolio report uses, now with an optional `property_id` parameter — not a duplicate method)
- `GET /properties/{id}/financial-dashboard` — Property Financial Dashboard (`reports.view`)
- `GET /properties/{id}/reports/cash-flow` — Property Cash Flow (Phase 10's `AccountingReportService`, `accounting.view`)
- `GET /properties/{id}/reports/income-statement` — Property Income Statement (the *same* `income_statement()` method Phase 10's portfolio report uses, with an optional `property_id` parameter)
- `GET /properties/{id}/reports/ledger` — Property Ledger (new: a per-property sub-ledger across every GL account it touched)
- `GET /properties/{id}/reports/balance-summary` — Property Balance Summary (new: like Trial Balance, but scoped to one property's own journal lines — intentionally *not* expected to net to zero on its own, since it's a subset of the full ledger)

Five of the seven reuse an **existing** report method with a new optional
`property_id` parameter (backward compatible — every existing portfolio-
wide call site is unaffected, verified by regression tests); only the
Ledger and Balance Summary needed genuinely new methods, since neither
has a natural portfolio-wide equivalent to extend.

Permissions split by which existing module actually owns the underlying
data: P&L, Expense, and Financial Dashboard reuse Phase 11's
`ReportsService` and are gated by `reports.view`; Cash Flow, Income
Statement, Ledger, and Balance Summary reuse Phase 10's
`AccountingReportService` and are gated by `accounting.view` — matching
each method's existing portfolio-wide sibling exactly, so Staff's access
level is unchanged (still no GL access, still full operational-report
access).

**Property Cash Flow** deliberately has no opening/closing bank balance
field (unlike the portfolio Cash Flow report) — cash isn't physically
segregated per property in this system, so instead of a fictional
per-property bank balance, it reports the property's own net cash
contribution (inflows minus outflows attributable to it), which is the
metric that's actually meaningful for a profit center.

### Enterprise Dashboard extension (post-Phase 11)

A new, richer analytics dashboard sitting **alongside** the original
Dashboard (`/dashboard`, unchanged and still in the sidebar) — the new
one lives at `/enterprise-dashboard`. No new backend module was created:
it's powered entirely by the **same** `GET /reports/analytics/dashboard`
endpoint (Phase 11's `dashboard_analytics`), extended additively:

- New optional `date_from`/`date_to` query parameters (default to "this
  month to date" exactly as before — calling with no parameters is
  byte-for-byte identical to the pre-extension behavior, verified by a
  regression test).
- New KPI fields on the existing `DashboardKPIs` schema: `total_units`,
  `occupied_units`, `vacant_units`, `occupancy_rate_percentage`,
  `contracts_expiring_soon`. Every original field is untouched.
- New top-level chart-data fields on `DashboardAnalyticsOut`:
  `properties_by_type`, `properties_by_availability`,
  `occupancy_by_type` (all reused directly from Phase 11's Property/
  Occupancy report methods), and `cash_flow_by_type` (reused from Phase
  10's `AccountingReportRepository.cash_flow_by_transaction_type` via a
  local cross-module import — the same pattern used throughout this
  codebase for report composition, not a duplicated query).

**Frontend**: `recharts` was added as a new dependency — the project had
no charting library before, and this dashboard explicitly needed real
Pie/Bar/Area/Line charts rather than the CSS-bar approximations used
elsewhere. Chart colors are pulled from `tailwind.config.js`'s existing
brand/amber/rust/ink palette and react to the existing `useTheme()`
context, so charts switch between light/dark styling using the exact
same theme system as the rest of the app — no new dark-mode
infrastructure. Interactive filters (period quick-select, custom date
range, property type) re-fetch the same endpoint with different query
parameters. "Real-time updates" is implemented as a 60-second auto-
refresh poll with a pause/resume control and a "updated Xs ago"
indicator — the backend has no WebSocket/SSE layer, and introducing one
for a single dashboard would be a disproportionate new subsystem, so
this is documented here as an honest interpretation rather than
implied to be a live push feed.

### Internationalization (i18n) extension (post-Phase 11)

Full English/Arabic internationalization, architected for unlimited
additional languages, added on both frontend and backend. Full details,
including an honest breakdown of exactly what's translated versus what
remains as documented follow-up work, are in
[`docs/i18n.md`](docs/i18n.md). In brief:

- **Frontend**: `react-i18next` + `i18next` (new dependencies — no i18n
  library existed before). Nine translation namespaces (`common`, `nav`,
  `auth`, `dashboard`, `properties`, `validation`, `reports`, `pdf`,
  `email`), each with English and Arabic files sharing **exactly** the
  same keys (verified by a scripted check — 283 keys, zero mismatches).
  A `LanguageSwitcher` component persists the selection to
  `localStorage` (`pms_language`, the same pattern already used for the
  theme) and calls `i18next.changeLanguage()`, which every component
  using `useTranslation()` is subscribed to — so switching is instant,
  with no page reload. Arabic sets `dir="rtl"` on `<html>`, and
  Tailwind's built-in `rtl:`/`ltr:` variants (core in 3.3+, no plugin)
  handle the highest-visibility layout mirroring (icon flipping,
  dropdown alignment) in the Sidebar/Navbar/Pagination.
- **Backend**: `app/core/i18n.py` — a flat `TRANSLATIONS` dict keyed by
  language code; adding a new language is one more dict entry, nothing
  else changes. Applied generically (not per-endpoint) in two places
  with very high leverage: every Pydantic validation error (422) across
  every existing and future endpoint gets a `localized_msg`, and the
  global HTTP exception handler translates any `HTTPException` whose
  `detail` happens to be a recognized key — while passing through every
  other raw string **completely unchanged**, which is what keeps every
  existing `raise HTTPException(detail="...")` call site across the
  whole codebase working exactly as before (verified by regression
  tests). The two highest-traffic error paths — permission-denied
  (every protected endpoint) and login/auth — were converted to use
  keys as the flagship example.
- **PDF exports and email templates**: neither feature exists yet in
  this codebase (confirmed during the initial audit — `.pdf` is only an
  accepted upload file extension, and `EmailStr` only validates email
  address *fields*; there's no PDF generation or SMTP integration
  anywhere). Translation namespaces (`pdf.json`, `email.json`) are
  staged with common document/email terms so that whichever future
  phase builds those features has a ready-made, unlimited-language
  namespace to consume immediately — but no placeholder feature was
  built just to have something to translate, since that would be scope
  creep beyond an internationalization phase.

### Enterprise Reporting extension (post-Phase 11)

The 10 requested report categories map onto Phase 11's `ReportsService`
and repository — 5 already existed (Property, Owner, Tenant, Occupancy,
Financial) and are reused completely unchanged; 5 were genuinely missing
and were added as new methods on that same existing service/repository:
**Lease** (covers both `RentalContract` and `LeaseAgreement`, the two
contract types this system already models — no new "lease" entity),
**Maintenance** (status/priority/category/contractor breakdowns, average
resolution time), **Collections** (rent due vs collected, monthly
trend, by-property), **Outstanding** (consolidates tenant and owner
outstanding balances into aging buckets: current, 1-30, 31-60, 61-90,
90+ days overdue), and **Contract Expiration** (itemized list of both
contract types expiring within a configurable window).

**PDF and Excel export** were both entirely new capabilities (confirmed
absent from the codebase during the initial audit). `fpdf2` and
`openpyxl` were added — both pure-Python, no system-level dependencies,
no Dockerfile changes needed. `app/services/report_export_service.py`
is deliberately generic: it turns a `title + summaries + tables`
document into PDF/Excel bytes without knowing what a Property Report
*means* — `ReportsService.report_to_document()` is the one place that
maps each report's dict into that shape. One export endpoint
(`GET /reports/{report_type}/export?format=pdf|excel`) serves all 10
report types via this registry, rather than 10 duplicated endpoints.

**Filtering and grouping** follow the pattern Phase 11 already
established: date ranges, `property_id`, status/priority query params,
and responses already grouped by the dimensions that matter (by status,
priority, category, contractor, property, aging bucket).

**Charts** were added to all 5 new report tabs using `recharts`.
**Printing** reuses a shared `ReportExportBar` component plus a
`@media print` block hiding app chrome (Tailwind's `print:` variant
handles per-element opt-outs).

**Export Scheduling** needed one genuinely new table — no existing table
represents "a saved recurring report export configuration."
`ReportSchedule` (migration `0012`) stores report type, format,
frequency, filters, and `next_run_at`/`last_run_at`. Running a schedule
stores the export through the **existing** `Attachment` +
`FileUploadService` mechanism (extended with `save_bytes()`), the same
pattern `AttachmentService.upload()` already uses. Honest scope note: no
SMTP exists in this codebase, so a schedule doesn't email anyone — it
generates and stores the file for download; there's also no background
job runner, so "on schedule" means an external cron or manual action
calling `run-due`. `reports.create/edit/delete` permissions already
existed since Phase 11 (seeded but never assigned) — this phase
completes that by assigning them to Branch Manager.

### UI Modernization (presentation-only pass)

Zero backend files were touched for this pass, and on the frontend, no
`useEffect`, API call, state variable, permission check, or routing
condition was changed anywhere — verified by diffing every edit against
this rule as it was made (e.g. `ProtectedRoute`'s three `if` conditions
are byte-identical to before; only the JSX each branch *renders* was
restyled). What changed is the design system and how loading/empty/error
states are presented.

**Why this reaches nearly the whole app despite touching relatively few
files**: this codebase already funnels almost everything through a
shared component layer (`components/ui.tsx`) and a shared Tailwind
component-class layer (`.btn`, `.card`, `.input`, `.badge`,
`.table-shell`, defined in `styles/index.css`). Upgrading those two
layers once means every consumer inherits the upgrade automatically —
41 files use `.btn-primary`/`.btn-secondary`, 30 use `.card`, 12 form
modals use the shared `Modal`, every paginated list uses the shared
`Pagination`. None of those 41/30/12/etc. files needed to be individually
edited to get refined hover/active states, smoother transitions, the
new scale-in modal animation, ESC-to-close, or the numbered pagination
strip.

- **Design tokens** (`tailwind.config.js`, additive): the existing
  brand/ink/amber/rust palette is untouched — it was already a
  deliberate, professional choice from Phase 1. Added: an
  `out-expo` easing curve, a `card-hover`/`floating`/`focus-brand`
  shadow scale, and five keyframe animations (fade-in, fade-in-up,
  scale-in, slide-in-right, shimmer).
- **Global CSS**: refined `.btn`/`.input`/`.card` with smoother
  transitions and subtle micro-interactions (active-state scale,
  hover shadow lift); sticky table headers; a `.skeleton` shimmer
  utility; a `prefers-reduced-motion` block that collapses every
  animation/transition to near-instant for anyone whose OS requests it
  (accessibility — this modernization pass doesn't force motion on
  people who've opted out).
- **New primitives in `ui.tsx`** (additive exports, all existing
  props/behavior on `PageHeader`/`StatusBadge`/`Pagination`/
  `EmptyState`/`Modal`/`ToolbarSearch` preserved exactly):
  `Skeleton`/`SkeletonText`/`SkeletonCard`/`SkeletonKpiGrid`/
  `SkeletonTable` for content-shaped loading states, `FormField` (an
  opt-in label+input+error/hint wrapper for "Better Forms" — existing
  hand-built forms keep working unchanged; this is available for new or
  updated ones), `Tooltip` (used on the collapsed sidebar's icon-only
  nav items, which had no accessible label at all before), and
  `RouteLoadingFallback` for the new route-level code splitting below.
- **Sidebar/Navbar/Layout**: refined transitions, a translucent sticky
  header, gradient avatar/logo treatment, and a genuine responsive-design
  fix — the mobile hamburger button already existed and was already
  wired to a handler, but had zero effect below the `md` breakpoint
  since the sidebar was unconditionally `hidden` there. It now opens a
  proper overlay drawer on mobile (backdrop, slide-in, closes on
  navigation or Escape via the shared click-outside pattern), while the
  desktop collapse/expand behavior is completely unchanged.
- **Performance**: every authenticated page is now `React.lazy()`-loaded
  with a single `Suspense` boundary inside `Layout` (so Sidebar/Navbar
  stay mounted and visible during a page's chunk download, only the
  content area shows the loading fallback) — Login and its two small
  auxiliary pages stay eagerly bundled since they're the first thing an
  unauthenticated person sees. `vite.config.ts` also splits React/
  recharts/i18next into separate vendor chunks for better long-term
  browser caching across deploys. Neither change alters what any route
  renders or how it behaves, only when its code downloads.
- **Accessibility**: focus-visible rings on every interactive element
  (already present, refined), `role`/`aria-label`/`aria-expanded`/
  `aria-current`/`aria-busy` added across the modal, pagination,
  skeletons, and notification/user menus; Escape closes the modal and
  focus moves into it on open; `index.html` gained a `description` meta
  tag, `theme-color` for both color schemes, and a `noscript` fallback.
- **Flagship examples of the new patterns applied end-to-end**:
  `DashboardPage` and `PropertiesPage` swap their old bare-spinner/dash-
  placeholder loading states for the new skeleton screens — genuinely
  presentational changes; their `useEffect`/`apiClient.get` calls are
  byte-identical to before. `LoginPage` gained a subtle entrance
  animation and background accent.

**What was intentionally left as-is**: the remaining ~25 pages keep
their original loading spinners rather than being individually
converted to skeleton screens — they still look correct and still work,
they just don't yet have the newest loading-state treatment. Converting
one follows the exact pattern shown in `PropertiesPage`: swap the
`<Loader2 className="animate-spin" />` block for `Skeleton`/
`SkeletonTable` markup shaped like that page's actual content, touching
nothing else. The color palette, typography scale, and responsive
breakpoint strategy were already solid from earlier phases and were
extended rather than replaced, consistent with "modernize" meaning a
refinement pass, not a rewrite.

### Rental Receipt Module

A two-phase addition — Phase 1 was analysis/architecture only (no code),
approved before any implementation began. Full design rationale,
decisions, and a complete field/endpoint reference are in
[`docs/rental-receipt-module.md`](docs/rental-receipt-module.md). In
brief: the existing `rental_payment_installments` table (one row per
contract per month, generated when a lease starts) turned out to already
be almost exactly what a "rental receipt" needs, so it was extended with
three columns (`receipt_number`, `printed_at`, `print_count` — migration
`0013`) rather than creating a new, competing entity. "Confirm Payment"
reuses `FinancialService.create_transaction()` completely unchanged.
Printing is browser-rendered (not a server PDF) specifically so the
receipt can reuse this app's existing Arabic RTL support end-to-end
rather than adding PDF bidi-shaping libraries. One new self-contained
utility was added (`app/core/number_to_words.py`, English + Arabic, for
the "amount in words" field) — nothing like it existed anywhere in the
codebase. Zero new permissions were needed: receipt actions reuse
`rentals.*`, and Confirm Payment reuses `financial.edit`, matching the
exact permission already used by the analogous `record_invoice_payment`
endpoint.

### Production Readiness Audit

A full codebase audit — dead code, N+1 queries, missing indexes,
security gaps, memory leaks, test coverage gaps — with real findings
fixed rather than just reported. Full report:
[`docs/production-audit-report.md`](docs/production-audit-report.md).
Headlines: a genuine test-infrastructure gap meant permission
enforcement (403) had almost no coverage anywhere in this codebase
despite being consistently implemented — fixed with a new non-superuser
test fixture and cross-module test file; a real N+1 query and one
missing index fixed; a genuinely unbounded `/notifications` endpoint
capped (with the mark-all-read edge case handled correctly); rate
limiting added to the login/password-reset endpoints; `/docs` was
unconditionally public in every environment, now gated by environment.
Also corrects an error from this project's own earlier documentation
(the i18n phase incorrectly noted the notifications router didn't
exist — it did, and does).

### Rent Billing Engine

A large spec asking for a "Rent Invoice" (billing document, full status
lifecycle) and separate "Payment Receipt," bulk generation across
configurable billing cycles, void/cancel with audit, QR verification,
and new reports/dashboard widgets. Pre-implementation analysis found
that "Rent Invoice" and "Payment Receipt" both already existed as the
`Invoice` and `Receipt` models from Phase 8 — extended (migration
`0015`), not duplicated. Billing cycles (monthly/quarterly/semi-annual/
annual/custom) already existed at the contract level too. Full design
rationale, explicit scope decisions (including why the invoice
numbering format and status lifecycle deliberately don't match the
spec's example literally, and why a full visual "Receipt Designer"
wasn't built), and API reference:
[`docs/rent-billing-engine.md`](docs/rent-billing-engine.md). The
pre-existing Rental Receipt Module (a separate, simpler system from an
earlier phase) is deliberately left untouched — both now coexist and
both are documented.

### Maintenance Contracts extension (post-Phase 9)

Phase 9 (Maintenance) only modeled *reactive* maintenance — a ticket
filed after something breaks. This adds the missing proactive
counterpart: `MaintenanceContract`, a recurring/annual service contract
with a Contractor (elevator inspections, HVAC/AC servicing, generator
servicing, fire-safety inspection, etc.), covering a Property for a
fixed term. Full design rationale and API reference:
[`docs/maintenance-contracts-module.md`](docs/maintenance-contracts-module.md).

New migration: `0024_maintenance_contracts.py` — the new
`maintenance_contracts` table, plus one additive nullable column,
`maintenance_requests.maintenance_contract_id`, so a work order can
optionally be linked back to the contract it was performed under (every
existing request is `NULL` and unaffected). No new permission
module — every new endpoint under `/maintenance/contracts/*` reuses the
existing `maintenance.view/create/edit/delete` permissions.

`MaintenanceContract` deliberately mirrors `LeaseAgreement`'s (Phase 3)
`draft → active → (expired | terminated | renewed)` status machine and
renewal-creates-a-new-row pattern, rather than inventing a new shape.
Contract expiry (`is_expiring_soon`) and the next scheduled service
visit (`is_service_due_soon` / `is_service_overdue`,
`next_service_due_date` advanced by `visit_frequency` each time
`POST /{id}/log-visit` is called) are tracked as two independent
concerns, since a year-long contract expiring and this quarter's
elevator inspection being due are different questions. The same
on-demand sweep pattern as Phase 3's renewal reminders applies here too
(`POST /maintenance/contracts/maintenance/run`) — no background job
scheduler exists in this stack, so this is exposed as an on-demand
endpoint pending a real cron/Azure Function timer trigger in production,
the same honest limitation already documented for the Phase 3 sweep.

Frontend: a new `/maintenance/contracts` page (list, filters, create
modal, and Activate/Log Visit/Renew/Terminate row actions), linked from
the existing Maintenance page's header alongside "Contractors &
Technicians." No existing maintenance page, route, or component
behavior was changed.

### Bulk Tenant Import extension (post-Phase 6)

Phase 6 (Tenant Management) only supported creating tenants one at a
time. This adds a two-step, per-building bulk path: download an
`.xlsx` template pre-filled with that building's units, fill in tenant
details next to each one, upload it back. Full design rationale (and
why it's tenant-only, all-or-nothing on upload, and scoped to one
building at a time) is in
[`docs/tenant-bulk-import.md`](docs/tenant-bulk-import.md).

No migration, no new table, no new permission — reuses the existing
`Tenant` model and `tenants.create` permission exactly as the
single-create endpoint does. Two new endpoints:
`GET /tenants/import-template/{building_id}` and
`POST /tenants/import/{building_id}`. Deliberately does **not** create
any Rental Contract — each row only ever creates a plain Tenant;
linking a tenant to a specific unit's contract stays the existing,
separate manual step.

Frontend: **a building's own page → Tenants tab → "Import Tenants from
Excel"** (`TenantImportModal.tsx`). No existing property or tenant
page/component behavior was changed beyond adding this one entry
point.

### Archive extension (post-Phase 3 Business Logic Review)

Every table already had a `status` column with `RecordStatus.ARCHIVED`
defined, but it was only ever reached as a side effect of
`soft_delete()` — "archive" and "delete" were the same action. Full
design rationale: [`docs/archive-extension.md`](docs/archive-extension.md).

New, alongside the existing (unchanged) `soft_delete()`/`restore()`:
`BaseRepository.archive()`/`.unarchive()`, which only ever set `status`
and never touch `deleted_at` — an archived record stays fully visible
everywhere except the list endpoints it's wired into (opt back in with
`include_archived=true`). Wired into Properties and both contract types
(`LeaseAgreement`, `RentalContract`): `POST /{id}/archive`,
`POST /{id}/unarchive`, plus an `include_archived` list param — no new
migration, no new permission (reuses `*.edit`). Since
`status='archived'` was previously unreachable except via
`soft_delete()` (which already hides the record via `deleted_at`
regardless), no existing record can already be "archived but not
deleted" — this changes zero existing query results until the new
Archive button is actually used.

Frontend: an Archive/Unarchive button on the Property, Lease, and
Rental Contract detail pages (next to Delete), and a "Show Archived"
checkbox on their list pages.

### Combined Rent Vouchers (multiple months, one voucher)

`GenerateVouchersRequest` gained one field, `combine: bool = False`.
When true, all the listed transactions (which must belong to the same
tenant) produce **one** voucher pair instead of one pair per
transaction — e.g. a tenant paying 3 months of rent at once. Two new
nullable columns on the existing `rent_vouchers` table carry this:
`extra_transaction_ids` (the additional transactions beyond the
primary one, comma-separated, display-only) and `combined_amount` (the
printed total). The printed period becomes a range — "January 2026 –
March 2026 (3 months)" — computed from the starting `rental_month` and
how many transactions were combined, rather than needing new
per-transaction month tracking. Everything else about `RentVoucher`
(the existing `UniqueConstraint(transaction_id, copy_type)`, the
non-combined generation path, the print template) is unchanged.

Deliberately scoped to **same-tenant, multiple months** only — not
multiple different units/properties on one voucher, which would need
the print template itself to show several different addresses and was
out of scope for this pass (see the conversation this followed for the
"keep it to one added checkbox, no new screens" constraint). Frontend:
a single checkbox in the existing "Generate Rent Vouchers" modal
(`RentVouchersPage.tsx`) — no new page or modal.

### Cascading Property Selector (post-Phase 3 Business Logic Review)

Replaces manual/flat property entry in both contract-creation forms
with a real Owner → Property → Floor → Apartment cascade. Full analysis
and design rationale: [`docs/cascading-property-selector.md`](docs/cascading-property-selector.md).

**Rental Contract form**: the flat, unfiltered 100-property dropdown is
now a proper cascade, scoped by owner/building at each step, with a
live occupied/vacant check (Phase 18 Occupancy Engine) shown before
submit. **Lease Agreement form**: `property_reference` was previously
a genuinely free-text field even though `LeaseAgreement.property_id`
has existed as a real FK since Phase 3 — the form just never used it.
It's now auto-filled from the same cascade (still editable, and still
the required field the model/printed documents expect) and the real
`property_id` is sent alongside it.

One small, necessary, additive backend change made this possible
without duplicating any query logic: `PropertyListItemOut` gained
`parent_property_id` (already on the detail schema, just missing from
the list one), and `GET /properties` gained an opt-in
`top_level_only=true` filter. Both are backward compatible — every
existing caller is unaffected.

### Dashboard Consolidation & Currency/Country UI Simplification

Full rationale: [`docs/dashboard-consolidation.md`](docs/dashboard-consolidation.md).

**Two dashboards → one.** `/dashboard` and `/enterprise-dashboard` were
genuinely two different pages, not accidental duplicates — but
confusing to navigate. Per the confirmed decision, `/enterprise-dashboard`
is retired (route commented out, page file untouched) and `/dashboard`
now carries the full requested layout: 7 top summary cards (Buildings,
Apartments, Occupied, Vacant, Active Contracts, Expiring Contracts,
Tenants), a Property Overview panel, a Tenant Overview panel, a
Contract Management panel (recent + expiring), and 5 Quick Action
buttons (the first three of which now deep-link into their target
page's existing create modal via a new `?new=true` param, rather than
duplicating any form). Every number is computed by reusing existing
Occupancy Engine and Rental Contract dashboard services — nothing was
re-derived. Previous system-admin widgets (users, roles, GL variance,
etc.) are kept, just collapsed under a "More system stats" toggle
instead of competing for top billing.

**Currency/Country: correction made before touching anything.** The
original ask was to delete the Currency and Country database tables.
Investigation showed `currency_id` is a real FK across 6 core financial
models (genuine multi-currency support, not decorative), and
`City.country_id` is a required FK — deleting either would have broken
contracts, receipts, and every property/owner/tenant address. The safe
alternative that was actually implemented: only the standalone
Currency/Country **management screens** are disabled (routes commented
out, Sidebar entries removed) — Cities stays, and Company Profile's
single default-currency/default-country pickers are untouched. No
model, migration, or endpoint was touched; this is a routing-only
change, fully reversible by uncommenting two lines.

### Pay Owner (real settlement + Owner Ledger, together)

Found during a system audit: the Owner Statement
(`docs/owner-ledger-engine.md`) already computes and displays an
"Owner Payments" line reducing what's owed to an owner — but there was
no way to actually create one. `OwnerLedgerTransactionType.OWNER_PAYMENT`
existed on the model; it just wasn't in `VALID_MANUAL_ENTRY_TYPES`, and
no endpoint exposed it. Separately, a fully-built integration service
already existed for exactly this —
`OwnerLedgerSettlementService.settle_and_record()`
(`app/business_workflows/owner_ledger/owner_settlement_service.py`,
itself explicitly documented as delegating to the existing, unmodified
Phase 12 `OwnerSettlementWorkflowService` rather than reimplementing
payout logic) — but its own docstring said "No new API endpoint calls
this directly in this phase... a future endpoint... uses it." That
endpoint didn't exist until now.

Added: `POST /leases/{lease_id}/installments/{installment_id}/settle`
— calls that existing service as-is. Creates the real Owner Payment
Transaction (with a receipt, exactly like the existing "Mark Paid"-
adjacent flow already did) **and** posts the matching Owner Ledger
entry in the same call, so the Owner Statement's balance actually
reflects it. No new business logic was written — this is purely a
missing endpoint being added to something that already worked.

The lease's existing "Mark Paid" button (a pure status flag — no
transaction, no ledger entry) is kept as-is, since removing it would
change existing behavior for anyone relying on that lighter-weight
flow. A new, clearly-labeled **"Pay Owner"** button sits next to it in
`LeaseDetailPage.tsx`'s installment table, opening a small form
(account, payment method, date) that calls the new endpoint.

### Reset Business Data script — scope extended to Financial Accounts + Accounting

`backend/reset_business_data.py` (see its own module docstring for the
full destructive-operation warnings and usage) originally, on
confirmed request, deliberately preserved Financial Accounts and the
Accounting setup (Chart of Accounts, Cost Centers, VAT Rates, Posting
Rules) — a follow-up confirmed those should be wiped too, to start
entirely from zero. The script's dependency graph was regenerated from
scratch against all 46 tables now in scope (up from 41) using the same
topological-sort verification as the original version, and re-checked
for any table outside that scope still referencing something being
deleted — one was found (`ReportSchedule.last_export_attachment_id` ->
`attachments`, since Attachments are deleted early) and is unlinked
(row kept) before deletion starts, same pattern as before.

### Bug fix: "Outstanding" totals were counting future, not-yet-due installments

Found via a real report from someone using the system: a 12-month
contract creates 12 monthly installments upfront (by design — the
schedule needs to exist ahead of time). Every "outstanding amount" /
"total due" query across the codebase summed *all* of those
`pending`/`overdue` installments with no `due_date` filter — so the
day a 12-month contract was signed, its **entire year's rent** showed
up as "outstanding," 11 months before 11 of those installments had
even come due.

Fixed by adding `due_date <= today` to every one of the 11 places this
exact query pattern was repeated across `rental_repository.py`,
`lease_repository.py`, `reports_repository.py`, and
`financial_repository.py` (found by grepping for the exact `.in_([...PENDING,
...OVERDUE])` pattern project-wide, not just the one instance that was
reported) — including the two "outstanding aging" reports, where a
future installment was previously landing in the "current" bucket
instead of being excluded entirely (a not-yet-due installment isn't
"outstanding," aging or otherwise). `DashboardService` and
`FinancialService.outstanding_balances()` both delegate to these same
repository methods, so the fix applies everywhere those numbers are
shown without needing separate changes there.

### Bug fix: deleting a record never checked for active dependents first

Reported directly: deleting an Owner, Tenant, Rental Contract, Master
Lease, or Property never refused, even when the thing being deleted
still had active dependents pointing at it (an Owner with active
Properties, a Tenant with an active contract, an active contract/lease
itself, a Property with active contracts or child units still
attached). Every `delete_*` service method just soft-deleted
unconditionally — none of them had ever checked.

This is why "nothing ever really disappears" was also true and by
design (see `reset_business_data.py`'s own docstring on why this
system never hard-deletes financial/legal records) — soft-delete never
errors at the database level even with active dependents, since the
row is never actually removed. That's correct for the delete itself,
but it meant nothing ever stopped a person from making an owner,
tenant, or contract vanish from every screen while other active
records still depended on it existing.

Fixed by adding an explicit dependent check to all five `delete_*`
methods (`OwnerService`, `TenantService`, `RentalService`,
`LeaseService`, `PropertyService`) — each now raises `409 Conflict`
with a specific, actionable message (e.g. "Cannot delete: this owner
has 2 active Master Lease(s). Terminate those first.") instead of
silently proceeding. The five detail-page delete buttons that call
these endpoints (`PropertyDetailPage.tsx`, `OwnerDetailPage.tsx`,
`TenantDetailPage.tsx`, `RentalDetailPage.tsx`, `LeaseDetailPage.tsx`)
were also updated to actually surface that message — none of them had
a try/catch around the delete call before, so the new 409 would have
failed silently in the browser console with no visible feedback.

### Bug fix: Collect Rent had no idea a month might already be paid

Reported directly, with a concrete scenario: collect a tenant's rent
through **Rent Collection → Quick**, then separately open that same
contract's **Payment Schedule** tab and press **Mark Paid** on the
same month — nothing stopped either action, so the same month could
end up double-counted (750 instead of 375, in the reported case).

Root cause: `CollectRentPage.tsx`'s Quick path had zero awareness of
`RentalPaymentInstallment` — it just posted a free-typed amount
straight to `POST /financial/transactions`, completely bypassing the
contract's own schedule. Meanwhile a **safe, already-built** endpoint
for exactly this — `POST /rentals/installments/{id}/confirm-payment`
— already existed with its own duplicate check
(`if inst.payment_status == "paid": raise 409`) but nothing on this
page called it.

Fixed by wiring Quick mode to that existing endpoint: selecting a
tenant now fetches their active contract's pending/overdue
installments and shows them as a pick list (falling back to a free
amount only when no schedule exists) instead of a bare amount field.
Picking one calls `confirm-payment`, which the already-paid ones can't
be picked for since they're filtered out of the list, and which the
backend itself refuses if picked anyway. `confirm-payment`'s response
was extended with `transaction_id` (additive — `RentalReceiptsPage`,
its only other caller, ignores the response body entirely) so the
voucher can still be generated immediately after, same as before.

The Payment Schedule tab's own "Mark Paid" button — a pure status
flag, no real transaction, same as the equivalent button on the Lease
side — is relabeled "Mark Paid Only" with an explanatory tooltip, same
reasoning as the Owner-side "Pay Owner" / "Mark Paid Only" split
documented above.

### New: printable, signable receipt for Owner Payments (and Tenant Payments)

Raised directly: an Owner Payment had a receipt NUMBER (`RCP-xxx`,
auto-issued the same as always) but no actual printable DOCUMENT — no
letterhead, no amount in words, no signature line, nothing to hand the
owner. `RentVoucherPrintPage` existed for tenant rent specifically;
nothing generic existed for everything else a `Receipt` row covers.

Added `ReceiptPrintPage.tsx` (`/receipts/{id}/print`) — a simpler,
single-document receipt (not the tenant/company 2-copy Rent Voucher
format, which was requested specifically for rent collection) showing
the amount in words in English and Arabic (reusing
`amount_to_words()` from `app/core/number_to_words.py`, the same
helper the Rent Voucher already uses — no duplicated logic), with a
"Prepared By" / "Owner Signature" (or "Received By" for tenant
payments) signature line. Backed by a new
`GET /financial/receipts/{id}/print-data` endpoint.

Wired up in three places: the Financial → Transactions table's RECEIPT
column is now a link straight to the print page; and both **Pay
Owner** flows (the Owner Ledger tab's general balance payment, and a
Master Lease installment's settlement) now open the receipt in a new
tab automatically right after a successful payment — closing the loop
the person asked for directly ("a button to pay the owner and print a
receipt for that, for signing").

### Closed: Financial → Record Transaction now has the same duplicate-payment protection

Follow-up to the section above: rather than leaving this as a warning
pointing elsewhere, `TransactionFormModal.tsx` now has the same
installment-picker `CollectRentPage.tsx` has. Picking Tenant Payment
or Owner Payment and a party fetches that party's pending/overdue
installments (already-paid ones aren't listed) and routes the save
through the same protected endpoints:
`POST /rentals/installments/{id}/confirm-payment` for a tenant,
`POST /leases/{leaseId}/installments/{id}/settle` for an owner's
Master Lease installment, or (new) `POST /owner-ledger/{id}/pay` when
the owner payment isn't tied to a specific Master Lease installment
but should still pay down their general Owner Ledger balance — all
three already refuse an already-settled entry. A successful Owner
Payment through either of the last two also opens the printable
receipt automatically, same as the dedicated Pay Owner buttons.

"Something else" is still available and still unprotected, by
design — a payment that genuinely isn't a normal scheduled
installment (e.g. a one-off adjustment) has nowhere else to go, so
this form still needs a free-form path; it just isn't the only path
anymore, and it isn't what's selected by default.

### Architecture decision: consolidated 5 overlapping "did this get paid" documents down to 2

Raised directly, after being asked to audit the sidebar for
overlapping functionality: this codebase had accumulated **five**
separate documents/numbering schemes all answering the same question
("has this month's rent been paid") for a tenant, built up in
different phases without ever being reconciled against each other:

1. **`RentalPaymentInstallment.receipt_number`** ("RR-xxx") — the
   original Rental Receipt Module. Not a real separate document, just
   a number stamped on the installment row itself.
2. **`RentVoucher`** ("RV-xxx") — the current, actively-developed
   bilingual printable voucher (QR code, PACI, signatures).
3. **`Receipt`** ("RCP-xxx") — a generic financial receipt,
   auto-issued for any tenant/owner payment not tied to an
   installment.
4. **`Invoice`** (Rent Billing Engine) — a *completely separate*
   billing pipeline (its own generation, its own status lifecycle)
   duplicating what `RentalPaymentInstallment` already tracks, for the
   same contracts.
5. **`PendingRentSlip`** ("PRS-xxx") — genuinely distinct (pre-
   collection vs. post-collection), kept as-is.

**Decision, confirmed directly: keep the Rent Cycle Engine's
`RentalPaymentInstallment` schedule as the one source of truth for
"what's due, when," and keep `RentVoucher` as the one proof-of-payment
document.** The Invoice/Rent Billing Engine and the old Rental Receipt
Module (RR-xxx) are retired from the UI.

**What actually changed** (the same "hide the front door, don't touch
the data" approach used throughout this codebase for
Currencies/Countries and Rent Billing before this — nothing here
drops a table, deletes a model, or removes a backend endpoint; all of
it is reversible):
- `CollectRentPage.tsx` — the "Full (with invoice)" mode and its
  entire Invoice/Payment-allocation code path are removed. The page is
  now just the installment-linked Quick flow, unconditionally.
- `FinancialPage.tsx` — the "Invoices" tab is removed from `TABS` (the
  tab's own component code is untouched, just unreached), and the
  "Rent Billing" header button is removed.
- `App.tsx` — the `/financial/rent-billing` route is commented out,
  same pattern as the Currencies/Countries routes above it.
- The Rental Receipt Module (`RentalReceiptsPage.tsx`,
  `RentalReceiptPrintPage.tsx`, `generate-monthly` receipt numbering)
  needed no further change — it was already unreachable from any nav
  link (see the earlier "orphaned feature" audit note), so it's
  already in the same de facto retired state as the rest of this
  decision, just via a different path.
- `TransactionFormModal.tsx`'s installment-picker (see the section
  above) already only ever talks to `RentalPaymentInstallment` and
  `LeasePaymentInstallment` — no Invoice-path code needed removing
  there.

The `Invoice` model, its migrations, its API endpoints, and any
historical Invoice rows already in a database are completely
untouched — only reachable via direct API calls now, not through any
page in the app.

### Executive Dashboard & Reporting Center (Phases 1–5)

Response to a large-scope redesign document (13 dashboard sections +
35+ reports). Rather than attempt every line shallowly, this was
executed in real, working phases — each one genuinely additive
(nothing existing removed or changed), each one built from real data
only (no placeholder numbers, no fake sparkline trends).

- **Phase 1** — `GET /dashboard/executive-summary` (new,
  `/dashboard/summary` untouched): 18 KPI cards, Rent Collection
  Overview, Occupancy donut chart (recharts), Financial Summary, Smart
  Alerts (each one only appears if its condition is actually true).
- **Phase 2** — `GET /dashboard/top-lists` and `GET /dashboard/calendar`:
  7 top lists (revenue, occupancy, tenants, owners, expenses, vacant
  units, late payments) and a 30-day upcoming-events feed pulled from
  4 genuinely separate existing date fields (rent due, contract end,
  maintenance scheduled_date, service contract next_service_due_date).
- **Phase 3** — `GET /search`: the Navbar's search input existed but
  had never been wired to anything — it was a static placeholder with
  no state or handler at all. Now searches Buildings/Units, Tenants,
  Owners, Contracts, Receipts, Expenses, Maintenance, and Payments,
  debounced, with results grouped by category.
- **Phase 4** — Dashboard Customization: a "Customize" panel to
  show/hide each section, saved to `localStorage`. Drag-and-drop
  reorder/resize was scoped out — it would need a DnD library that
  isn't a dependency of this project, and adding one for this alone
  didn't seem worth it without being asked specifically.
- **Phase 5** — Reporting Center audit + gap-fill: **17 of the
  requested 35 report types already existed and were already wired to
  ReportsPage.tsx tabs** (Financial, Income, Expenses, Profit,
  Occupancy, Units, Vacancy, Properties, Tenants, Owners, Leases,
  Maintenance, Collections, Outstanding, Contract Expirations,
  Executive Summary/Analytics, plus PDF/Excel export and scheduled
  recurring exports — all pre-existing infrastructure, not part of
  this redesign). Four genuinely missing report types were added using
  that same existing registry pattern (`REPORT_TYPES` /
  `generate_report()` / `report_to_document()` in
  `reports_service.py`, which is what makes the generic
  `/{report_type}/export` endpoint and the Scheduled Exports feature
  work for every report type without a duplicated endpoint each):
  **Owner Balance Report**, **Tenant Ledger** (also covers Tenant
  Payment History / Tenant Statement), **Security Deposit Report**,
  and **Renewed Contracts Report**. Each is a new tab in
  `ReportsPage.tsx` using the existing `ReportExportBar` component
  (also pre-existing — a duplicate export-button component was written
  first and then removed once this was found) so PDF/Excel export and
  scheduling work identically to every other report.

**Deliberately not attempted, and why:**
- **Custom Report Builder** — this is its own mini BI tool (an
  arbitrary field/filter/grouping composer), not a report; a real
  version is a multi-week project on its own, not a gap-fill item.
- **Unit History / Building History** as dedicated reports — the data
  exists (ActivityLog, filterable by entity), but a genuinely useful
  version needs deciding what counts as "history" for a unit (every
  occupancy change? every maintenance event? every transaction?)
  rather than guessing that scope unprompted.
- **Drag/resize/reorder dashboard widgets** — see Phase 4 above.
- Sparkline charts on every KPI card (from the original ask) — no
  historical daily snapshot table exists to source them honestly; a
  real month-over-month % change is shown where it can be computed
  truthfully instead (see Phase 1).
