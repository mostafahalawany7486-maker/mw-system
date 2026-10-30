# Phase 1 — User Acceptance Testing (UAT) Script

Walk through these scenarios end-to-end as a business stakeholder, not a
developer. Each scenario states **Steps**, **Expected Result**, and a
pass/fail box.

---

### UAT-1: First login and account safety
**Steps:**
1. Go to the app URL, sign in as `admin@pms-demo.com` / `Admin@12345`.
2. Try signing in again with an intentionally wrong password 5 times.
3. Try the correct password on the 6th attempt.

**Expected Result:** Login succeeds on step 1. Step 3 is rejected with a
"locked" message, even though the password is correct — protecting the
account from brute-force attempts.
Pass ⬜ Fail ⬜

---

### UAT-2: Set up the company
**Steps:**
1. Navigate to Company Profile.
2. Fill in legal name, email, phone, address, and select a country/city/base currency.
3. Save.
4. Refresh the page.

**Expected Result:** All entered data persists after refresh and appears
exactly as entered.
Pass ⬜ Fail ⬜

---

### UAT-3: Open a new branch
**Steps:**
1. Navigate to Branches → Add Branch.
2. Enter a name and a branch code that's already in use ("HO").
3. Correct the code to something unique and save.

**Expected Result:** Step 2 is rejected with a clear "code already exists"
message. Step 3 succeeds and the new branch appears in the list.
Pass ⬜ Fail ⬜

---

### UAT-4: Bring a new employee onboard with the right access
**Steps:**
1. Navigate to Roles → confirm "Branch Manager" and "Staff" exist.
2. Navigate to Users → Add User. Create a new user, assign the "Staff" role.
3. Log out, log in as that new user.
4. Attempt to open the Users page as this new user.

**Expected Result:** The new user can log in with the temporary password.
The Users nav item is not visible to them (Staff role has no `users.view`),
and directly hitting the Users API returns "access denied."
Pass ⬜ Fail ⬜

---

### UAT-5: An employee leaves the company
**Steps:**
1. As Administrator, find the test user from UAT-4.
2. Deactivate them.
3. Attempt to log in as that user.

**Expected Result:** Login is rejected with an "account inactive, contact
your administrator" message. The user still appears in the system (for
historical record-keeping) but marked inactive.
Pass ⬜ Fail ⬜

---

### UAT-6: Forgotten password recovery
**Steps:**
1. Log out. On the login page, click "Forgot password?"
2. Enter the test user's email, submit.
3. Use the reset link/token to set a new password.
4. Log in with the new password.

**Expected Result:** A confirmation message appears regardless of whether
the email is registered (privacy-safe). The reset completes and the new
password works; the old one no longer does.
Pass ⬜ Fail ⬜

---

### UAT-7: Custom role for a specialized job function
**Steps:**
1. As Administrator, go to Roles → Add Role, name it "Front Desk", and grant
   only `branches.view` and `company.view`.
2. Assign this role to a user.
3. Log in as that user and confirm the sidebar only shows Dashboard, Company
   Profile, and Branches.

**Expected Result:** The sidebar and API access exactly match the granted
permissions — nothing more, nothing less.
Pass ⬜ Fail ⬜

---

### UAT-8: Uploading a supporting document
**Steps:**
1. On any record (e.g. a Note or test entity), upload a PDF under 25MB.
2. Try uploading a `.exe` file.
3. Try uploading a 30MB file.

**Expected Result:** Step 1 succeeds and the file is retrievable. Steps 2
and 3 are both rejected with clear, specific error messages.
Pass ⬜ Fail ⬜

---

### UAT-9: Knowing who did what
**Steps:**
1. As Administrator, make a handful of changes (edit a user, edit company
   profile, create a branch).
2. Navigate to Activity Log and Audit Log.

**Expected Result:** Activity Log shows a plain-English history. Audit Log
(visible to Administrator only) shows exactly which fields changed, from
what value to what value, with a timestamp and IP address.
Pass ⬜ Fail ⬜

---

### UAT-10: Working comfortably on a phone
**Steps:**
1. Open the app on a phone (or resize a desktop browser to ~375px wide).
2. Navigate through Dashboard, Users, and Company Profile.
3. Toggle dark mode.

**Expected Result:** Every screen is usable without horizontal scrolling or
overlapping elements. Dark mode applies consistently and persists after
closing/reopening the browser.
Pass ⬜ Fail ⬜

---

## Sign-off

| Scenario | Tester | Date | Result |
|---|---|---|---|
| UAT-1 | | | |
| UAT-2 | | | |
| UAT-3 | | | |
| UAT-4 | | | |
| UAT-5 | | | |
| UAT-6 | | | |
| UAT-7 | | | |
| UAT-8 | | | |
| UAT-9 | | | |
| UAT-10 | | | |

**Overall Phase 1 approval:** ⬜ Approved to proceed to Phase 2  ⬜ Changes requested
