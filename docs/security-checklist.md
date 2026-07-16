# Phase 1 — Security Checklist

## Authentication & session
- [x] Passwords hashed with bcrypt (via passlib), never stored or logged in plaintext
- [x] JWT access tokens are short-lived (30 min default); refresh tokens longer-lived (7 days) and used only to mint new access tokens
- [x] Account lockout after 5 failed login attempts (15-minute cooldown) — brute-force mitigation
- [x] Password reset tokens are single-purpose (`type: password_reset`), short-lived (60 min), and cannot be reused as access tokens
- [x] Forgot-password endpoint never reveals whether an email is registered
- [x] Password strength enforced server-side (min 8 chars; reset flow additionally requires upper/lower/digit) — never trust client-side validation alone
- [ ] **Before production:** move `SECRET_KEY` out of `.env` into Azure Key Vault; rotate it from the placeholder in `.env.example`
- [ ] **Before production:** add a `Content-Security-Policy` header (Nginx layer) to reduce XSS blast radius, since tokens are in `localStorage`
- [ ] **Recommended for Phase 2+:** add a server-side refresh-token blocklist (Redis) for immediate revocation on logout/compromise

## Authorization (RBAC)
- [x] Every mutating and most read endpoints are gated by `PermissionChecker(<code>)`, enforced server-side (never trust the frontend hiding a button)
- [x] Superuser bypass is explicit and auditable (`is_superuser` flag), not implicit via a wildcard role name
- [x] System roles cannot be deleted/renamed/disabled, preventing accidental lockout of all admin access
- [x] Soft-deleted users cannot authenticate (`get_by_email` filters `deleted_at IS NULL`)

## Input validation & injection protection
- [x] All request bodies validated via Pydantic schemas (type + constraint checking) before reaching business logic
- [x] All database access goes through SQLAlchemy's parameterized query builder — no raw string-interpolated SQL anywhere in the codebase
- [x] File upload validates extension allow-list and size limit before writing to storage
- [x] React escapes all rendered content by default (no `dangerouslySetInnerHTML` used anywhere in Phase 1 code) — mitigates stored XSS from user-entered text (notes, names, etc.)

## Transport & infrastructure
- [ ] **Before production:** terminate TLS at the Azure App Service / Front Door layer; enforce HTTPS-only (`Strict-Transport-Security` header)
- [x] CORS is allow-listed to specific origins (`BACKEND_CORS_ORIGINS`), not wildcarded
- [ ] **Before production:** restrict PostgreSQL firewall rules to only the backend's outbound IP range (Azure Private Link / VNet integration recommended over public endpoint + firewall rules)
- [x] File storage backend is abstracted (`local` vs `azure_blob`) so production never writes user uploads to the app server's local disk (which wouldn't survive horizontal scaling anyway)
- [ ] **Before production:** enable Azure Blob Storage soft-delete / versioning for uploaded attachments as an extra recovery layer beyond the app's own soft-delete

## Auditability
- [x] Every create/update/delete/login/logout/password action writes an Activity Log entry
- [x] Security-relevant actions (login, logout, password changes, user/role changes) additionally write an Audit Log entry with field-level before/after diffs, actor, IP address, and user agent
- [x] Audit Log is read-only via the API (no update/delete endpoints exist for it) and restricted to `audit.view`

## Secrets management
- [x] `.env` files are gitignored; `.env.example` contains only placeholders, no real secrets
- [ ] **Before production:** confirm no real secrets were ever committed to version control history; rotate anything that was
- [ ] **Before production:** use Azure Key Vault (or App Service's built-in App Settings, backed by Key Vault references) for `SECRET_KEY`, `DATABASE_URL`, and `AZURE_STORAGE_CONNECTION_STRING`

## Dependency hygiene
- [ ] Run `pip-audit` / `npm audit` before each release and address high/critical findings
- [ ] Pin dependency versions (already done in `requirements.txt` / `package.json`) and review changelogs before bumping major versions
