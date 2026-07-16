# Phase 1 — Performance Checklist

## Database
- [x] Every table has an index on `id` (PK) and `uuid` (unique index)
- [x] Foreign key columns used in filters (`role_id`, `branch_id`, `country_id`, etc.) are indexed via their FK constraint
- [x] Polymorphic tables (`attachments`, `notes`, `activity_logs`, `audit_logs`) have a composite index on `(entity_type, entity_id)` — the access pattern used everywhere
- [x] `users.email` has a unique index (used on every login)
- [x] Connection pooling configured (`pool_size=10, max_overflow=20, pool_pre_ping=True`) to survive Azure PostgreSQL failover without stale connections
- [ ] **Action for Phase 2+:** add composite indexes as new query patterns emerge (e.g. lease status + branch once Leases exist)
- [x] User list endpoint eager-loads `role` + `permissions` in one extra query (avoids N+1)
- [ ] **Action:** add `EXPLAIN ANALYZE` review to the deployment checklist once real data volumes exist

## API
- [x] Pagination is enforced on every list endpoint (`page_size` capped at `MAX_PAGE_SIZE=100`) — prevents unbounded result sets
- [x] Search uses indexed `ILIKE` on a small, deliberate field set per entity, not full-table scans across all columns
- [x] `X-Process-Time-Ms` response header added for lightweight per-request latency visibility (check via browser devtools or `curl -i`)
- [ ] **Action for Phase 2+:** add Redis-backed response caching for read-heavy, rarely-changing lookups (countries, currencies)
- [ ] **Action:** add rate limiting (e.g. via Azure API Management or `slowapi`) before production launch, particularly on `/auth/login` and `/auth/forgot-password`

## Frontend
- [x] Vite build produces hashed, cache-friendly static assets; Nginx config sets `Cache-Control: public, immutable` for `/assets/`
- [x] Gzip compression enabled in the Nginx production config
- [x] Lists are paginated client-side (10 rows/page default) instead of rendering unbounded tables
- [ ] **Action for Phase 2+:** introduce route-based code-splitting (`React.lazy`) once the page count grows substantially
- [ ] **Action:** add a CDN in front of the static frontend build in production (Azure Front Door / CDN)

## Load & scaling readiness (validate before go-live)
- [ ] Run a basic load test (e.g. `k6` or `locust`) against `/auth/login` and the busiest list endpoints at expected concurrent-user levels
- [ ] Confirm the backend is stateless (no in-memory session state) so it can run multiple replicas behind a load balancer — **true by design** in Phase 1 (JWT auth, no server-side session)
- [ ] Confirm `uvicorn --workers N` or a process manager (Gunicorn+Uvicorn workers) is used in production, not a single dev worker
