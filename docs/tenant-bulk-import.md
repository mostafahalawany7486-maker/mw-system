# Bulk Tenant Import (per building)

## What this adds

Phase 6 (Tenant Management) only supported creating tenants one at a
time via the form. This adds a two-step bulk path, scoped to a single
building at a time (deliberately — simpler and more accurate than a
multi-building spreadsheet):

1. `GET /tenants/import-template/{building_id}` — downloads a
   pre-filled `.xlsx` listing every existing unit of that building
   (unit number, floor, unit type — reference only), with blank
   columns for tenant details next to each one.
2. Fill it in, then `POST /tenants/import/{building_id}` (multipart
   file upload) — creates one `Tenant` record per filled row.

## Scope decisions (from the conversation that specified this)

- **One building per file.** Not a multi-building workbook — simpler
  to generate, and the unit list stays accurate to one building.
- **Tenant records only — no Rental Contract is created.** Linking an
  imported tenant to a specific unit's contract stays a deliberate,
  separate manual step via the existing Phase 7 flow. The template's
  unit columns are for the person filling it in to know which row is
  which — they are not written anywhere or used to auto-link anything.
- **All-or-nothing on upload.** Every row is validated first with zero
  database writes; if *any* row fails, nothing is created and the
  response lists every failing row + reason so the whole file can be
  fixed and re-uploaded in one pass. Once every row passes, all
  tenants are created in a single transaction (one commit at the end;
  any unexpected failure mid-batch rolls back everything).

## Per-row validation rules

- `Tenant Type` must be exactly `individual` or `company` (a
  spreadsheet dropdown is provided on that column to reduce typos).
- `individual` rows require First Name + Last Name; `company` rows
  require Company Name.
- Primary Phone and Primary Email are optional.
- `National ID`, if given, must be unique — checked against both the
  existing database *and* other rows in the same file (a duplicate
  within the file is caught before anything is created, not just
  against already-committed data).
- A row left completely blank (every fillable column empty) is
  silently skipped, not treated as an error — the template pre-fills
  one row per unit whether or not the user has a tenant for it yet.

## Implementation notes

- No new table/migration — reuses the existing `Tenant` model and
  `TenantRepository.next_tenant_code()` exactly as the single-create
  endpoint does (called once per row, inside the same open
  transaction — each `repository.create()` call already `flush()`es,
  so the count-based numbering stays correct across the whole batch
  without a full commit between rows).
- No new permission module — both endpoints reuse the existing
  `tenants.create` permission, same as every other Tenant Management
  endpoint.
- Column order in the generated template is authoritative for reading
  it back (matched by position, not by parsing header text) since the
  same code generates and parses it. If a template is hand-edited to
  reorder columns, download a fresh one instead of trying to fix the
  old one.
- Frontend: **Building's own page → Tenants tab → "Import Tenants from
  Excel"** (`TenantImportModal.tsx`) — download step, upload step,
  and a clear per-row error list if the upload is rejected. No
  existing property/tenant page or component behavior was changed
  beyond adding this one entry point.
