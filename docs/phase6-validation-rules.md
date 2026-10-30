# Phase 6 — Tenant Management: Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Tenant
| Field | Rule |
|---|---|
| `tenant_type` | Required, must be `individual` or `company` |
| `first_name`, `last_name` | Required **if** `tenant_type=individual` (422 if missing) |
| `company_name` | Required **if** `tenant_type=company` (422 if missing) |
| `national_id` | Optional; unique across active tenants if provided (409 on duplicate) |
| `passport_number` | Optional, no uniqueness constraint (some jurisdictions reissue numbers; national ID is the primary uniqueness anchor) |
| `commercial_registration_number` | Optional, no uniqueness constraint enforced at this layer |
| `primary_email` | Valid email format if provided |
| `tenant_code` | System-generated (`TNT-000001` sequence), never client-supplied, immutable |
| Delete | Soft-delete only; sub-resources (contacts, emergency contacts, documents, ratings) are preserved for history, not hard-deleted |

## Tenant Contact / Emergency Contact
| Field | Rule |
|---|---|
| `full_name` (both) | Required |
| `phone` (emergency contact only) | Required — general Contacts allow an optional phone, but an Emergency Contact without a phone number defeats its purpose |
| `is_primary` | At most one `true` per tenant per sub-resource type — enforced server-side, same "auto-unset previous primary" pattern as Owner sub-resources (Phase 2) |

## Tenant Document
| Field | Rule |
|---|---|
| `document_type` | Free-text convention: `national_id`, `passport`, `commercial_registration`, `visa`, `other` |
| File | Same allow-list and size limit as every other upload in the system |
| `expiry_date` in the past | Surfaces as `is_expired: true` (informational flag only) |

## Tenant Rating
| Field | Rule |
|---|---|
| `rating_value` | Required, integer, must be between 1 and 5 inclusive (422 otherwise) |
| `comment` | Optional free text |
| Average | Computed at read time as the mean of all non-deleted ratings for that tenant — never stored/cached, so it's always current and recalculates correctly when a rating is added or removed |

## Blacklist
| Rule |
|---|
| Blacklisting requires a non-empty `reason` (422 if blank/whitespace-only) |
| Blacklisting an already-blacklisted tenant → 409 |
| Unblacklisting a tenant that isn't blacklisted → 409 |
| Blacklisting/unblacklisting both require `tenants.edit` — there is no separate `tenants.blacklist` permission, matching the precedent set by lease status transitions (Phase 3) reusing `leases.edit` |
| `blacklisted_at` and `blacklisted_by` are set automatically server-side (never client-supplied) and fully cleared on unblacklist |

## Cross-cutting
- All sub-resources (contacts, emergency contacts, documents, ratings) require `tenants.edit` to create/update/delete, and `tenants.view` to read — the whole Tenant aggregate is treated as one permission unit, same pattern as Owner (Phase 2) and Property (Phase 4/5).
