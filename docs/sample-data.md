# Phase 1 — Sample / Seed Data

> **Note (Fresh Start change — see the main [README](../README.md#fresh-start-no-demo-business-data)):**
> as of that change, a fresh `python seed.py` run no longer creates any
> of the Owners/Tenants/Properties/Leases/Rental Contracts/Financial/
> Maintenance/Accounting sample data or the Maria Manager / Sam Staff
> demo logins described below — only foundational/setup data
> (permissions, roles, lookups, Amenities catalog, the Administrator
> account). Everything on this page describes the **old, richer demo
> dataset**, which still exists at
> `backend/seed_with_demo_data.py.bak` for anyone who wants it back
> (sales demos, QA/staging environments). Copy it back over `seed.py`
> (or run it directly) to get everything described below.

Running `python seed.py` (done automatically by `docker-compose up`) creates
the following. The script is idempotent — safe to re-run.

## Accounts
| Name | Email | Password | Role |
|---|---|---|---|
| System Administrator | `admin@pms-demo.com` | `Admin@12345` | Administrator (superuser) |
| Maria Manager | `maria.manager@pms-demo.com` | `ChangeMe!123` | Branch Manager |
| Sam Staff | `sam.staff@pms-demo.com` | `ChangeMe!123` | Staff |

## Roles
- **Administrator** — every permission, system role, cannot be deleted
- **Branch Manager** — view-level access across most modules
- **Staff** — view-level access to lookup/reference data only

## Permissions
36 permissions auto-generated as `{module}.{action}` for the 9 Phase 1
modules × 4 actions (view/create/edit/delete) — see `docs/permissions-matrix.md`.

## Lookup data
- **Countries:** United States, United Arab Emirates, United Kingdom
- **Cities:** New York, Los Angeles, Chicago (US) · Dubai, Abu Dhabi (UAE) · London, Manchester (UK)
- **Currencies:** USD (base), AED, GBP
- **System Settings:** `date_format`, `theme_default`, `session_timeout_minutes`, `company_name_display`

## Organization
- **Company Profile:** "PMS Leasing Company LLC" with a sample US address
- **Branch:** "Head Office" (code `HO`), marked as head office, located in New York

## Property Owners (Phase 2)
- **OWN-000001** — Robert Chen (individual), mailing address in Los Angeles, one primary bank account
- **OWN-000002** — Skyline Holdings LLC (company), mailing address in Dubai, one primary contact (Amira Al-Farsi, Asset Manager)

## Lease Agreements (Phase 3)
- **LSE-000001** — Active, owner Robert Chen, monthly rent $2,500, mid-term (started 180 days ago, ends in ~185 days)
- **LSE-000002** — Draft, owner Skyline Holdings LLC, quarterly rent $45,000, 3-year commercial lease pending signature

## Properties (Phase 4)
- **PRP-000001** — Sunset Villa (villa), owner Robert Chen, Los Angeles, linked as the current property on LSE-000001
- **PRP-000002** — Business Bay Tower (building), owner Skyline Holdings LLC, Dubai, linked on LSE-000002
- **PRP-000003** — Floor 3 Office Suite (office), a unit inside PRP-000002
- **PRP-000004** — Al Quoz Warehouse 12 (warehouse), owner Skyline Holdings LLC, standalone
- **Amenities catalog** — 12 seeded items (Swimming Pool, Gym, Parking, Elevator, 24/7 Security, CCTV, Central AC, Balcony, Furnished, Pet Friendly, Loading Dock, Fire Safety System)

## Unit Management (Phase 5)
- **Floors** — Floor 3, 4, 5 created under PRP-000002 (Business Bay Tower)
- **Building Management extension** — open PRP-000002's detail page to see
  the live Building Summary widget (floors/units/occupied/vacant/leases/
  tenants/maintenance) and the Leases/Tenants/Maintenance tabs; PRP-000003
  (a unit inside it) already has activity flowing through from later
  phases, so the building-level aggregation has real data to show
- **PRP-000005** — Basement Parking Spot 12, a unit inside PRP-000002
- **PRP-000006** — Storage Unit 3, a unit inside PRP-000002
- **PRP-000003** (the office unit) — now has `unit_number="301"`, `rent_price=15000.00`, electricity/water meter numbers, is assigned to Floor 3, and has both the parking spot (PRP-000005) and storage unit (PRP-000006) linked to it

## Tenants (Phase 6)
- **TNT-000001** — Laura Martinez (individual), national ID + passport on file, one primary emergency contact (Carlos Martinez, spouse)
- **TNT-000002** — Northwind Logistics FZE (company), commercial registration on file, one primary contact (Farah Al-Sayed, Operations Manager)
- **TNT-000003** — Derek Voss (individual), **blacklisted** — "Repeated late rent payments and property damage at previous unit."

## Rental Contracts (Phase 7)
- **RNT-000001** — Active, tenant Laura Martinez subleasing Sunset Villa (PRP-000001), monthly rent $3,200 with a $100 fixed loyalty discount and a $50 fixed late fee (5-day grace). Property availability is `leased` as a result.
- **RNT-000002** — Draft, tenant Northwind Logistics FZE subleasing the Al Quoz Warehouse (PRP-000004), quarterly rent $18,000 with a 5% tax rate and a 2% late fee (7-day grace), pending signature.

## Financial Management (Phase 8)
- **ACC-000001** — Petty Cash — Head Office (cash), $2,000 opening balance
- **ACC-000002** — Main Operating Account (bank, First National Bank), $50,000 opening balance
- **TXN-000001** — Tenant payment: $3,100 from Laura Martinez against RNT-000001, into the bank account, with auto-issued receipt **RCP-000001**
- **TXN-000002** — Owner payment: $2,500 to Robert Chen (LSE-000001), out of the bank account, with auto-issued receipt **RCP-000002**
- **TXN-000003** — Expense: $450 plumbing repair at Sunset Villa, out of Petty Cash
- **TXN-000004** — Income: $150 guest parking fee at Business Bay Tower, into Petty Cash
- **TXN-000005 / TXN-000006** — Linked transfer pair: $500 from the bank account into Petty Cash
- **INV-000001** — Draft invoice for Laura Martinez's next month's rent ($3,100), due in 15 days

## Maintenance (Phase 9)
- **CON-000001** — CoolBreeze HVAC Services (contractor, specialty: hvac, contact Amir Hassan)
- **TEC-000001** — Yusuf Odeh, in-house plumbing technician (no contractor affiliation)
- **TEC-000002** — Priya Nair, HVAC technician employed by CoolBreeze HVAC Services
- **MNT-000001** — Completed: kitchen sink leak at Sunset Villa, reported by Laura Martinez. 2 materials (P-trap fitting, sealant tape) + 1 labor entry (2.5h @ $45) logged by Yusuf Odeh
- **MNT-000002** — In Progress, urgent: HVAC unit not cooling at the Al Quoz Warehouse. Assigned to CoolBreeze / Priya Nair, 1 labor entry logged for initial diagnostics
- **MNT-000003** — Reported, unassigned: loading dock light out at the Al Quoz Warehouse
- No before/after photos are seeded — upload one manually via the UI to verify that flow (seeding real image bytes from a script isn't practical; this is a documented limitation, not a bug)

## Maintenance Contracts (post-Phase 9 extension)
- **CON-000002** — SkyLift Elevator Services (contractor, specialty: elevator, contact Nadia Fares)
- **MTC-000001** — Active annual elevator maintenance contract on property PRP-000002 (the seeded building), quarterly visits, $8,400/year, next visit due in ~25 days
- **MTC-000002** — Active annual AC maintenance contract on Sunset Villa, semi-annual visits, $1,200/year, using the existing CON-000001 (CoolBreeze) contractor, next visit due in ~10 days
- Neither contract has a linked `MaintenanceRequest` seeded — create one via the UI/API with `maintenance_contract_id` set to see a work order tied back to a contract

## Accounting (Phase 10)
- 15-account chart of accounts: 1000 Assets → 1100 Current Assets → **1110 Cash on Hand** / **1120 Bank - Operating Account**; 2000 Liabilities → 2100 Current Liabilities → **2110 Security Deposits Held** / **2200 VAT Control**; 3000 Equity → **3100 Retained Earnings**; 4000 Revenue → **4100 Rental Income** / **4200 Other Income**; 5000 Expenses → **5100 Maintenance Expense** / **5200 Owner Disbursements** / **5300 Refunds Issued** / **5900 General Operating Expense**
- ACC-000001 (Petty Cash) and ACC-000002 (Main Operating Account) from Phase 8 are linked to GL accounts 1110/1120
- **CC-000001** Sunset Villa Operations (linked to PRP-000001), **CC-000002** Warehouse Operations (linked to PRP-000004)
- **STD5** Standard Rate 5% (linked to 2200 VAT Control), **ZERO0** Zero-Rated 0%
- 8 posting rules mapping Phase 8 transaction types to GL offset accounts (tenant_payment→4100, owner_payment→5200, expense→5900 with a maintenance-specific override to 5100, income→4200, deposit_received/deposit_refund→2110, refund→5300) — deliberately VAT-free by default
- **JE-000001** — Posted opening-balances entry matching Phase 8's seeded $2,000 cash + $50,000 bank
- **JE-000002 / JE-000003** — Posted system-style entries demonstrating what Automatic Posting produces for TXN-000001 (tenant payment) and TXN-000002 (owner payment)
- **JE-000004** — A draft entry, useful for exercising the post/delete-draft workflow

## Reports (Phase 11)
No new sample data — Phase 11 adds no tables and no seed entities.
Every report is computed live from the sample data seeded by Phases 1–10
above (properties, tenants, owners, rental/lease contracts, financial
transactions, maintenance costs). Simply browsing to Reports after a
fresh `python seed.py` run is enough to see every report populated with
realistic figures.

## Property Profit Center extension (post-Phase 11)
No new sample entities — the existing TXN-000001 through TXN-000004,
INV-000001, and JE-000002/JE-000003 were backfilled with `property_id`
(PRP-000001 Sunset Villa, or PRP-000002 Business Bay Tower where the
description already named it) so the new per-property reports have
meaningful data immediately. Open PRP-000001's detail page → Financials
tab to see its Financial Dashboard populated with real figures.

## Enterprise Reporting extension (post-Phase 11)
3 sample `ReportSchedule` rows: a monthly Financial PDF, a weekly
Maintenance Excel, and a daily Collections PDF (seeded inactive, so it
doesn't clutter a fresh demo with "overdue" schedules). None have been
run yet (`last_run_at` is null) — use "Run Now" on the Scheduled Exports
tab to generate a real file and see it attach.

## Rental Receipt Module
Two sample installments seeded for RNT-000001 (Laura Martinez, Sunset
Villa): `RR-000001` for last month (fully confirmed/paid, printed once)
and `RR-000002` for this month (generated and printed, still awaiting
payment confirmation) — demonstrates both ends of the workflow
immediately after a fresh seed. Open Rentals → Rental Receipts to see
both, or print `RR-000002` to see the bilingual receipt document.

## Rent Billing Engine
`INV-000002` for Laura Martinez (Sunset Villa) demonstrates the new
capabilities alongside the original simple `INV-000001`: a full
snapshot, `monthly` billing cycle, partial payment (1,500 of 3,100
paid, status `partially_paid`), a QR verification token, and one
recorded print. Open Financial → Rent Billing to see it, or use
Generate Invoices for a fresh period to see the bulk engine run against
the seeded active lease.

## Using this data for testing
Log in as each of the three seeded accounts to verify RBAC boundaries hold
(see `docs/uat-script.md` UAT-4). Use the seeded countries/cities/currencies
to test the Branches and Company Profile dropdowns without needing to
create reference data manually first.
