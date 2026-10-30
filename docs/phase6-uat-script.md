# Phase 6 — Tenant Management: User Acceptance Testing (UAT) Script

---

### UAT-1: Onboard a new individual tenant
**Steps:**
1. Go to Tenants → Add Tenant.
2. Choose "Individual", enter a first/last name, National ID, and Passport
   Number.
3. Save, then add an Emergency Contact (name, relationship, phone).

**Expected Result:** The tenant appears with an auto-generated code
(`TNT-000004`). Both ID numbers are visible on the Overview tab. The
emergency contact appears on its own tab, separate from general contacts.
Pass ⬜ Fail ⬜

---

### UAT-2: Onboard a company tenant with multiple contacts
**Steps:**
1. Add Tenant → "Company", enter a company name and Commercial
   Registration Number.
2. Add two contacts: a Finance contact and an Operations contact, marking
   Finance as primary.

**Expected Result:** Both contacts appear; only Finance shows "Primary."
Commercial Registration Number is visible on the Overview tab.
Pass ⬜ Fail ⬜

---

### UAT-3: Blacklist a problem tenant
**Steps:**
1. Open a tenant, click "Blacklist," and enter a reason (e.g. "Repeated
   late payments").
2. Try clicking "Blacklist" again.

**Expected Result:** The tenant now shows a red "Blacklisted" badge
everywhere it appears (list and detail page), with the reason clearly
displayed. The second blacklist attempt is rejected — a tenant can't be
blacklisted twice.
Pass ⬜ Fail ⬜

---

### UAT-4: Give a tenant a second chance
**Steps:**
1. On the blacklisted tenant from UAT-3, click "Remove from Blacklist."

**Expected Result:** The blacklist badge and warning banner disappear
immediately; the tenant is now treated as being in good standing.
Pass ⬜ Fail ⬜

---

### UAT-5: Rate a tenant after a lease ends
**Steps:**
1. On any tenant, go to the Rating tab and add a rating (e.g. 4 stars)
   with a comment about their payment history.
2. Add a second rating from a different visit (e.g. 5 stars).

**Expected Result:** Both ratings appear in the list with their comments
and dates. The average (4.5) shows at the top of the tab and on the
tenant's list row.
Pass ⬜ Fail ⬜

---

### UAT-6: Find a tenant by any identifying detail
**Steps:**
1. On the Tenants list, search using: a partial name, a national ID
   number, and a phone number (three separate searches).
2. Filter to show only blacklisted tenants.

**Expected Result:** Each search correctly finds the matching tenant(s).
The blacklist filter narrows the list to just TNT-000003 (the seeded
blacklisted tenant) plus any others you've blacklisted during testing.
Pass ⬜ Fail ⬜

---

### UAT-7: Role boundaries hold for tenant data
**Steps:**
1. Log in as the seeded Staff user.
2. Open Tenants, then open a tenant's detail page.

**Expected Result:** Staff can view tenants, their documents, contacts,
and ratings, but sees no Add/Edit/Delete/Blacklist/Rate controls anywhere.
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

**Overall Phase 6 approval:** ⬜ Approved to proceed to Phase 7  ⬜ Changes requested
