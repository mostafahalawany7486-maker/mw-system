# Phase 9 — Maintenance: Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Design Overview
Materials and Labor Cost are per-request line items rather than single
guessed totals — "actual cost" is always `sum(materials) + sum(labor)`,
computed live, so it can never drift from what was actually logged.
Before/After photos get first-class fields (`photo_type` discriminator)
rather than being folded into the generic Phase 1 Attachment table, since
"before vs. after" is a specific, structured concept. History reuses the
generic Phase 1 ActivityLog — no new table needed.

## Contractors
| Field | Rule |
|---|---|
| `company_name` | Required |
| `specialty` | Optional; if given, must be one of the fixed set (plumbing, electrical, hvac, appliance, structural, pest_control, painting, cleaning, security, elevator, landscaping, general, other) |
| `contractor_code` | System-generated (`CON-000001` sequence), immutable |
| Deletion | Blocked (409) if any technician still references this contractor — reassign or remove those technicians first |

## Technicians
| Field | Rule |
|---|---|
| `first_name` / `last_name` | Required |
| `contractor_id` | Optional; if given, must reference an existing contractor (400 otherwise). Absent = in-house staff (`is_in_house: true`) |
| `specialty` | Same fixed set as Contractor |
| `technician_code` | System-generated (`TEC-000001` sequence), immutable |

## Maintenance Request
| Field | Rule |
|---|---|
| `property_id` | Required, must reference an existing property (400 otherwise) |
| `tenant_id` | Optional — a request need not be tenant-reported (e.g. staff-initiated inspections); if given, must reference an existing tenant |
| `priority` | One of `low`, `medium`, `high`, `urgent` (default `medium`) |
| `category` | Optional; same fixed set used for Contractor/Technician specialty |
| `scheduled_date` | Must not be before `reported_date` (422 otherwise) |
| `request_number` | System-generated (`MNT-000001` sequence), immutable |
| Editing | Blocked (409) once a request is `completed` or `cancelled` |

## Status Machine
| From | Allowed next states |
|---|---|
| `reported` | `assigned`, `cancelled` |
| `assigned` | `in_progress`, `on_hold`, `cancelled` |
| `in_progress` | `on_hold`, `completed`, `cancelled` |
| `on_hold` | `in_progress`, `cancelled` |
| `completed` | none (terminal) |
| `cancelled` | none (terminal) |

Any transition not listed above returns 409 with the current status and
the valid next steps, so the client can build accurate UI without
guessing. `hold` requires a reason; `cancel` requires a reason; `complete`
requires a completion date. The Assign action can be used again on an
already-`assigned`/`in_progress`/`on_hold` request to reassign or add a
technician alongside an existing contractor — it doesn't reset progress.

## Materials
| Rule |
|---|
| `quantity` and `unit_cost` must be ≥ 0 (422 otherwise) |
| `total_cost = quantity × unit_cost`, computed live, never stored redundantly |

## Labor Cost
| Rule |
|---|
| `hours` and `hourly_rate` must be ≥ 0 (422 otherwise) |
| A labor entry can reference a specific `technician_id`, a `contractor_id` (billed generally, no named individual), both, or neither — flexible enough to match how invoices actually arrive from vendors |
| `total_cost = hours × hourly_rate`, computed live |

## Photos
| Rule |
|---|
| `photo_type` must be exactly `before` or `after` (400 otherwise) |
| Reuses the exact same file validation as Phase 1 Attachments — allowed extensions and max size enforced by the shared `FileUploadService` |
| No cap on the number of before/after photos per request |

## Cross-cutting
- History reuses the generic Phase 1 ActivityLog (`entity_type="maintenance_request"`) — no new table, no new code path.
- Outstanding "actual cost" figures on the Maintenance dashboard only count `completed` requests within the current month, so partial/in-progress cost estimates don't distort monthly reporting.
