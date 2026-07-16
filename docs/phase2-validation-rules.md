# Phase 2 — Property Owners: Validation Rules

Adds to (does not replace) `docs/validation-rules.md`.

## Owner
| Field | Rule |
|---|---|
| `owner_type` | Required, must be `individual` or `company` |
| `first_name`, `last_name` | Required **if** `owner_type=individual` (422 if missing) |
| `company_name` | Required **if** `owner_type=company` (422 if missing) |
| `national_id` | Optional; unique across active owners if provided (409 on duplicate) |
| `primary_email` | Valid email format if provided |
| `owner_code` | System-generated (`OWN-000001` sequence), never client-supplied, immutable after creation |
| Delete | Soft-delete only; sub-resources (addresses/bank accounts/contacts/documents) are preserved for audit history, not hard-deleted |

## Owner Address / Bank Account / Contact
| Field | Rule |
|---|---|
| `line1` (address) | Required |
| `bank_name`, `account_holder_name` (bank account) | Required |
| `full_name` (contact) | Required |
| `is_primary` | At most one `true` per owner per sub-resource type — enforced server-side: setting a new primary automatically un-sets the previous one in the same transaction |

## Owner Document
| Field | Rule |
|---|---|
| `document_type` | Required, one of: `id_card`, `passport`, `trade_license`, `tax_certificate`, `poa`, `other` |
| File | Same allow-list and size limit as Phase 1 Attachments (`ALLOWED_UPLOAD_EXTENSIONS`, `MAX_UPLOAD_SIZE_MB`) |
| `expiry_date` | Optional; when in the past, the API exposes `is_expired: true` for the frontend to flag it — no automatic workflow action yet (reserved for a future phase's notification/reminder system) |

## Cross-cutting
- Every owner sub-resource mutation requires `owners.edit` (view-only roles cannot add/edit/delete addresses, bank accounts, contacts, or documents even though those are technically "sub-objects" — the permission model treats the whole Owner aggregate as one unit for simplicity in Phase 2).
- Owner deletion requires `owners.delete`, distinct from `owners.edit`, so a role can be allowed to manage owner details without being able to remove them entirely.
