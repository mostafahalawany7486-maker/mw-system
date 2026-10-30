# Phase 1 — Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

## 1. Environment & Health
- [ ] `docker-compose up --build` starts db, backend, frontend without errors
- [ ] `GET /health` returns `{"status": "healthy", ...}`
- [ ] Swagger docs load at `/api/v1/docs`
- [ ] Frontend loads at `http://localhost:5173` and redirects `/` → `/login` when logged out

## 2. Authentication
- [ ] Login with seeded admin (`admin@pms-demo.com` / `Admin@12345`) succeeds, redirects to Dashboard
- [ ] Login with wrong password returns 401 and shows an inline error
- [ ] Login with unknown email returns 401 (does not reveal whether the email exists)
- [ ] 5 consecutive failed logins locks the account (HTTP 423); correct password also rejected while locked
- [ ] Locked account unlocks automatically after the lockout window (15 min) OR via password reset
- [ ] `GET /auth/me` with a valid token returns the current user + permissions
- [ ] `GET /auth/me` without a token returns 401
- [ ] Logout clears local tokens and redirects to `/login`; protected pages become inaccessible
- [ ] Access token expiry triggers an automatic silent refresh (shorten `ACCESS_TOKEN_EXPIRE_MINUTES` temporarily to confirm)
- [ ] Expired/invalid refresh token forces logout and redirect to `/login`
- [ ] "Forgot password" with a registered email returns a generic success message (dev mode also echoes a token for testing)
- [ ] "Forgot password" with an unregistered email returns the same generic success message (no leak)
- [ ] Reset-password with a valid token changes the password; old password stops working, new one works
- [ ] Reset-password with an expired/invalid token returns 400
- [ ] Change-password (logged in) with wrong current password returns 400
- [ ] Password validation rejects passwords under 8 characters, and (for reset) requires upper/lower/digit

## 3. User Management
- [ ] List users: pagination, search (name/email), and sorting all work
- [ ] Create user with valid data succeeds; appears in list immediately
- [ ] Create user with duplicate email returns 409
- [ ] Create user with a password under 8 characters is rejected client- and server-side
- [ ] Edit user (name, phone, role, branch) saves and reflects immediately
- [ ] Deactivate user: `is_active=false`; deactivated user cannot log in (403)
- [ ] Reactivate user restores login ability
- [ ] Delete (soft-delete) user: disappears from default list, `deleted_at` set, not returned by `GET /users/{id}`
- [ ] A user without `users.view` permission gets 403 on `GET /users`

## 4. Roles & Permissions
- [ ] List roles shows seeded Administrator / Branch Manager / Staff with correct permission counts
- [ ] Create a new custom role with a subset of permissions; assign to a test user; confirm that user can only access the granted modules
- [ ] Edit role: change name/description/permissions; changes take effect on next login or token refresh (permissions are embedded in the access token)
- [ ] Attempt to rename/disable a system role (`is_system_role=true`) → 403
- [ ] Attempt to delete a system role → 403
- [ ] Attempt to delete a role that has users assigned → 409
- [ ] Delete an unused custom role → succeeds

## 5. Dashboard
- [ ] Widgets show correct counts (total/active users, roles, branches, unread notifications) matching DB state
- [ ] Recent activity feed shows the 10 most recent activity log entries, newest first
- [ ] Dashboard loads for any authenticated user regardless of role (no permission gate)

## 6. Company Profile
- [ ] First load with no profile configured returns a friendly "not configured" state in UI
- [ ] Save creates the profile; reload confirms persistence
- [ ] Edit updates existing profile (upsert, not duplicate rows)
- [ ] Country/City/Base Currency dropdowns populate from seeded lookup data
- [ ] A user without `company.edit` sees read-only fields; API rejects writes with 403

## 7. Branches
- [ ] Create branch with a duplicate code → 409
- [ ] CRUD (create/edit/delete) all work and persist
- [ ] "Head office" flag displays correctly in the list
- [ ] City dropdown reflects seeded cities

## 8. Countries / Cities / Currencies
- [ ] CRUD works for all three
- [ ] Cities correctly filter/display by parent country
- [ ] Currency `is_base_currency` toggle and exchange rate save correctly
- [ ] Search box filters results as expected on each page

## 9. System Settings
- [ ] Seeded settings (`date_format`, `theme_default`, `session_timeout_minutes`, `company_name_display`) display grouped by category
- [ ] Editing a setting value persists and is reflected after page reload
- [ ] Settings marked `is_editable=false` are not editable via UI or API (403 on attempted edit)

## 10. File Upload Service
- [ ] Upload a valid file type (pdf/png/jpg/docx/xlsx/csv/txt) under the size limit → succeeds, returns a URL
- [ ] Upload a disallowed extension (e.g. `.exe`) → 400
- [ ] Upload a file exceeding `MAX_UPLOAD_SIZE_MB` → 400
- [ ] Uploaded file is retrievable via its returned URL
- [ ] Delete an attachment removes both the DB record and the underlying file

## 11. Notes
- [ ] Add a note to a test entity; appears in the note list for that entity, newest/pinned first
- [ ] Pin a note; it sorts above unpinned notes
- [ ] Edit and delete a note both work

## 12. Activity Log & Audit Log
- [ ] Every create/update/delete/login/logout/password action produces an Activity Log entry with a human-readable description
- [ ] Sensitive/compliance-relevant actions also produce an Audit Log entry with a field-level diff (`changed_fields`)
- [ ] Audit Log is only visible to users with `audit.view`; others get 403
- [ ] Audit Log records `ip_address` on login/logout

## 13. Notifications
- [ ] A password-reset request creates an in-app notification for that user
- [ ] Unread count badge on the navbar matches `GET /notifications/unread-count`
- [ ] Marking a notification read updates its state and decrements the unread count
- [ ] "Mark all as read" clears the badge

## 14. UI / Responsive / Theming
- [ ] Sidebar collapses/expands via the navbar toggle
- [ ] Sidebar nav items are filtered by the current user's permissions (e.g. Staff doesn't see Users)
- [ ] Dark mode toggle persists across reloads (localStorage) and respects system preference on first load
- [ ] Layout is usable on a mobile viewport (375px width) — sidebar hides, content remains readable
- [ ] All tables show pagination controls when results exceed one page
- [ ] Empty states render correctly when a list has zero results
- [ ] Loading spinners show during data fetches, not blank screens

## 15. Security spot-checks
- [ ] JWT tokens are not stored in cookies without `httpOnly`/`secure` in production (Phase 1 uses localStorage; documented as a known tradeoff — see Security Checklist)
- [ ] All list/detail endpoints reject unauthenticated requests (401)
- [ ] All mutating endpoints reject requests lacking the relevant permission (403)
- [ ] SQL injection attempt in a search field (`' OR '1'='1`) returns zero results, not an error or data leak
- [ ] XSS attempt in a text field (e.g. Note content `<script>alert(1)</script>`) is stored/escaped safely and does not execute when rendered

## 16. Automated tests
- [ ] `pytest` passes all tests in `backend/tests/` (auth flows, user CRUD, RBAC enforcement)
