# Phase 1 — Validation Rules

All validation is enforced **server-side** (Pydantic schemas + service-layer
checks) as the source of truth; the frontend mirrors the same rules for a
responsive UX, but the API never trusts the client.

## Authentication
| Field | Rule |
|---|---|
| `email` | Valid email format (`EmailStr`); case-insensitive uniqueness across users |
| `password` (new user) | Minimum 8 characters |
| `new_password` (reset/change) | Minimum 8 characters, at least 1 uppercase, 1 lowercase, 1 digit |
| Login attempts | Account locks for 15 minutes after 5 consecutive failures |

## Users
| Field | Rule |
|---|---|
| `email` | Required, valid format, unique (409 on duplicate) |
| `first_name`, `last_name` | Required, non-empty |
| `role_id` | Must reference an existing role if provided |
| Delete | Soft-delete only; hard-delete is never exposed via the API |

## Roles
| Field | Rule |
|---|---|
| `name` | Required, unique (409 on duplicate) |
| System roles | Cannot be renamed, disabled, or deleted (403) |
| Delete | Blocked if any user is still assigned to the role (409) |

## Branches
| Field | Rule |
|---|---|
| `name`, `code` | Required |
| `code` | Unique across branches (409 on duplicate) |

## Countries
| Field | Rule |
|---|---|
| `name` | Required, unique |
| `iso_code2` | Required, unique, 2 characters |
| `iso_code3` | Required, unique, 3 characters |

## Cities
| Field | Rule |
|---|---|
| `name` | Required |
| `country_id` | Required, must reference an existing country |

## Currencies
| Field | Rule |
|---|---|
| `code` | Required, unique, 3 characters (ISO 4217) |
| `exchange_rate_to_base` | Numeric, defaults to 1.0 |

## Company Profile
| Field | Rule |
|---|---|
| `legal_name` | Required |
| `email` | Valid email format if provided |
| Record shape | Singleton — `PUT` upserts the single active profile row rather than creating duplicates |

## System Settings
| Field | Rule |
|---|---|
| `value` | Free text; interpretation depends on `value_type` (string/number/boolean/json) |
| Edit | Rejected (403) if `is_editable=false` on that setting |

## File Uploads
| Rule | Value |
|---|---|
| Allowed extensions | `.pdf .png .jpg .jpeg .doc .docx .xls .xlsx .csv .txt` (configurable via `ALLOWED_UPLOAD_EXTENSIONS`) |
| Max size | 25MB by default (configurable via `MAX_UPLOAD_SIZE_MB`) |

## Cross-cutting
- Every `PaginationParams.page_size` is capped at `MAX_PAGE_SIZE` (100) server-side, regardless of what the client requests.
- Every mutating endpoint requires the caller to hold the matching `module.action` permission (see `docs/permissions-matrix.md`), enforced by the `PermissionChecker` dependency — not just hidden in the UI.
