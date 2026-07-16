# Phase 1 — Bug Checklist Template

Log any issue found during testing here before reporting back. Use one row
per bug.

| ID | Area | Steps to Reproduce | Expected | Actual | Severity | Status |
|---|---|---|---|---|---|---|
| BUG-001 | e.g. Auth | e.g. Login with valid creds | Redirect to dashboard | Blank screen | High | Open |

**Severity guide:**
- **Critical** — blocks core functionality or is a security issue (e.g. RBAC bypass, data loss)
- **High** — a feature doesn't work as specified, no workaround
- **Medium** — feature works but has a UX/validation issue, workaround exists
- **Low** — cosmetic issue, typo, minor styling inconsistency

**Status values:** Open → In Progress → Fixed → Verified → Closed

## Known Phase 1 limitations (not bugs — by design, revisit in later phases)
- Logout is stateless (JWT is discarded client-side); a compromised access
  token remains valid until it naturally expires (≤30 min default). A
  server-side token blocklist (e.g. Redis) is a good Phase 2+ addition if
  immediate revocation becomes a requirement.
- JWTs are stored in `localStorage` on the frontend, which is vulnerable to
  XSS-based token theft. This is a common tradeoff for SPA + API architectures;
  mitigated by strict input escaping (React escapes by default) and a
  Content-Security-Policy header, which should be added at the Nginx/CDN
  layer in production (see Security Checklist).
- Email delivery is not wired up yet (forgot-password returns the raw token
  only in `APP_ENV=development`, for testability). Wire up an email provider
  (SendGrid, Azure Communication Services, etc.) before production launch.
- Dashboard widgets are system-level (users/roles/branches) since no
  business entities (properties, leases) exist yet; this is expected and
  will expand as Property/Lease/Tenant modules are built in later phases.
