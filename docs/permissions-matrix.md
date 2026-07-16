# Permissions Matrix — Phase 1

Permission codes follow `module.action`. Superusers (`is_superuser = true`)
bypass all checks. Non-superusers need the exact code on their assigned role.

## Modules & actions seeded in Phase 1

| Module | view | create | edit | delete |
|---|---|---|---|---|
| users | ✅ | ✅ | ✅ | ✅ |
| roles | ✅ | ✅ | ✅ | ✅ |
| branches | ✅ | ✅ | ✅ | ✅ |
| countries | ✅ | ✅ | ✅ | ✅ |
| cities | ✅ | ✅ | ✅ | ✅ |
| currencies | ✅ | ✅ | ✅ | ✅ |
| company | ✅ | – | ✅ | – |
| settings | ✅ | – | ✅ | – |
| audit | ✅ | – | – | – |
| owners | ✅ | ✅ | ✅ | ✅ |

(`company` and `settings` are singleton/global resources, so only `view`
and `edit` apply. `audit` is read-only by design.)

## Seeded system roles

| Role | Permissions |
|---|---|
| **Administrator** | All permissions (`is_superuser = true`, bypasses checks entirely) |
| **Branch Manager** | `users.view`, `branches.view`, `countries.view`, `cities.view`, `currencies.view`, `company.view`, `settings.view`, `owners.view`, `owners.create`, `owners.edit` |
| **Staff** | `branches.view`, `countries.view`, `cities.view`, `currencies.view`, `company.view`, `owners.view` |

System roles (`is_system_role = true`) cannot be renamed, disabled, or
deleted — this is enforced server-side in `RoleService`, not just hidden in
the UI, so it can't be bypassed via direct API calls.

## Extending permissions in future phases

Every new module (Properties, Lease Agreements, Tenants, Subleases, …)
should register `module.view / create / edit / delete` (and any custom
actions, e.g. `leases.approve`) in `seed.py`'s `MODULES` list, then assign
them to the appropriate roles. No code changes are needed elsewhere — the
`PermissionChecker` dependency and the `RoleService` permission editor UI
already work generically against the `permissions` table.
