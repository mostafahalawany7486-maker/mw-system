# Phase 5 — Unit Management: Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Floor
| Field | Rule |
|---|---|
| `floor_number` | Required (free text — supports "1", "G", "M", "PH", etc., not restricted to integers) |
| Parent | A floor can only be created under a property with `property_type="building"` (400 otherwise) |
| Delete | Blocked (409) if any non-deleted property still references this floor via `floor_id` — prevents orphaning units |

## Unit Fields (on Property)
| Field | Rule |
|---|---|
| `unit_number` | Optional free text, indexed for search, no uniqueness constraint (different buildings may reuse numbering) |
| `rent_price` | Optional, must be ≥ 0. This is the **asking/listed price**, intentionally separate from a Lease Agreement's `rent_amount` (Phase 3), which is the actual contracted figure — the two may differ and both are tracked independently |
| `electricity_meter_number`, `water_meter_number` | Optional free text, no format validation (utility providers use varied formats across jurisdictions) |
| `floor_id` | Optional; if provided, must reference an existing floor (400 if invalid). No enforcement that the floor's building matches the unit's `parent_property_id` — left flexible for edge cases (e.g. re-parenting), but the UI only ever offers floors from the unit's own parent building |
| `parking_space_id` | Optional; if provided, must reference an existing property with `property_type="parking"` (400 otherwise) |
| `storage_space_id` | Optional; if provided, must reference an existing property with `property_type="storage"` (400 otherwise) |
| Self-reference | A property cannot set its own ID as `parking_space_id` or `storage_space_id` (400) |

## Cross-cutting
- All new fields are nullable additions to the existing `properties` table — no Phase 4 data or behavior is affected.
- `floor_label`, `parking_space_code`, and `storage_space_code` in API responses are computed at read time (never stored), so they can never go stale relative to the referenced records.
