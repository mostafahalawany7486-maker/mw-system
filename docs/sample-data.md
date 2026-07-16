# Phase 1 — Sample / Seed Data

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

## Using this data for testing
Log in as each of the three seeded accounts to verify RBAC boundaries hold
(see `docs/uat-script.md` UAT-4). Use the seeded countries/cities/currencies
to test the Branches and Company Profile dropdowns without needing to
create reference data manually first.
