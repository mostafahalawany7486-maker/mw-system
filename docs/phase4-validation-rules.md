# Phase 4 — Property Management: Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Property
| Field | Rule |
|---|---|
| `property_type` | Required, one of `building`, `villa`, `apartment`, `commercial_unit`, `warehouse`, `shop`, `office`, `land`, `parking`, `storage` |
| `title` | Required |
| `owner_id` | Required, must reference an existing, non-deleted owner (400 if invalid) |
| `parent_property_id` | Optional; if provided, must reference an existing property (400 if invalid). No enforced type constraint (e.g. the API doesn't require the parent to specifically be a `building`) — the UI only offers Buildings as parent options for clarity, but the API stays flexible |
| `property_code` | System-generated (`PRP-000001` sequence), never client-supplied, immutable |
| `internal_code` | Optional free text, no uniqueness constraint (different branches may reuse internal numbering schemes) |
| `latitude` | Optional, must be between -90 and 90 |
| `longitude` | Optional, must be between -180 and 180 |
| `availability_status` | One of `available`, `leased`, `reserved`, `under_maintenance`, `off_market` |
| `furnishing_status` | Optional, one of `furnished`, `semi_furnished`, `unfurnished` |

## Property Images
| Rule |
|---|
| Only files with an `image/*` MIME type are accepted on the Images endpoint (400 otherwise, with guidance to use Documents instead) |
| At most one image per property can have `is_cover=true` — setting a new cover automatically un-sets the previous one, same pattern as Owner sub-resource "primary" flags (Phase 2) |
| Same size limit as all other uploads (`MAX_UPLOAD_SIZE_MB`) |

## Property Documents
| Rule |
|---|
| `document_type` free text convention: `title_deed`, `floor_plan`, `permit`, `inspection_report`, `other` (not server-enforced as an exact enum, unlike Owner documents in Phase 2, to allow flexibility for jurisdiction-specific document types) |
| Same allow-list/size limits as all other uploads |
| `expiry_date` in the past → `is_expired: true` in the API response (informational only, no automated workflow yet — consistent with the "informational flag, not enforcement" pattern used for Owner document expiry in Phase 2) |

## Amenities
| Rule |
|---|
| `name` required, unique (409 on duplicate) |
| Assigning amenities to a property (`amenity_ids`) fully replaces the previous set on each update — it is not additive/incremental |

## Current Lease Contract (computed, not stored)
- A property's "current lease" is computed at read time: the most recent `active`-status lease (Phase 3) whose `property_id` matches this property. It is never a stored/cached field, so it can never go stale.
- A property can have zero or one *current* (active) lease at a time, but many leases over its lifetime (expired, terminated, renewed ones remain in history, just not surfaced as "current").
