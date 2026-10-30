# Phase 3 — Renewal Reminders: How They Actually Work (and What's Missing)

## Current behavior (Phase 1–3)

There is **no background job scheduler** in the stack yet (no Celery, no
cron container, no Azure Function timer). Renewal reminders — and the
related "auto-expire past-due leases" / "flag overdue installments" logic —
are implemented as an **idempotent, on-demand sweep**:

```
POST /api/v1/leases/maintenance/run
```

This endpoint (permission: `leases.edit`):
1. Flips `active` leases whose `end_date` has passed to `expired`.
2. Flips `pending` installments whose `due_date` has passed to `overdue`.
3. For every `active` lease within its own `renewal_notice_days` window
   that hasn't already been reminded (`renewal_reminder_sent = false`),
   sends an in-app Notification to every active Administrator and marks
   the lease as reminded (so re-running the sweep doesn't spam).

The frontend exposes this as a "Check Renewals" button on the Leases page.
This is honest and correct, but it depends on someone actually clicking
the button (or calling the endpoint) — it will not run itself.

## What's needed for real production use

Wire the same endpoint to a real scheduler so it runs automatically, once
a day. Two straightforward options:

### Option A: Azure Function (Timer Trigger) — recommended for this stack
Since deployment already targets Azure Container Apps, add a small Azure
Function (Consumption plan, Timer Trigger, e.g. `0 0 6 * * *` for 6am
daily) that does nothing but:
```python
import requests
requests.post(
    f"{BACKEND_URL}/api/v1/leases/maintenance/run",
    headers={"Authorization": f"Bearer {SERVICE_ACCOUNT_TOKEN}"},
)
```
This requires creating a dedicated service account user (a non-interactive
`User` row with a long-lived token or, better, a machine-to-machine auth
scheme) — not built in Phase 1–3. Track this as a Phase 4+ item if the
business wants this automated rather than manually triggered.

### Option B: Simple cron container
Add a lightweight `cron` sidecar (or a scheduled Container App Job in
Azure) that runs the same `curl -X POST .../maintenance/run` on a
schedule. Simpler to stand up than Option A, less "cloud-native," but
works identically.

### Option C (not recommended for production, fine for a demo)
A polling approach from the frontend while any admin has the app open.
This was deliberately NOT implemented — it's fragile (only works while
someone has a browser tab open) and was explicitly avoided in favor of the
honest manual-trigger approach documented above.

## Why this wasn't built into Phase 3 directly

Phase 1's foundation (see `docs/deployment-azure.md`) doesn't provision a
job scheduler, message queue, or Functions app — none of that was in
scope for "Project Foundation." Bolting on a scheduler dependency inside a
single Phase 3 feature would mean either (a) silently expanding Phase 1's
infrastructure without approval, or (b) shipping something that claims to
"send renewal reminders automatically" but actually doesn't, if the
infra isn't there to run it. Exposing it as an honest, working, on-demand
endpoint — with this document explaining exactly what's needed to
automate it — was the more transparent choice for a phase-gated,
approve-before-continuing workflow.
