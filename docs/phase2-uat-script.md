# Phase 2 — Property Owners: User Acceptance Testing (UAT) Script

---

### UAT-1: Onboard an individual property owner
**Steps:**
1. Go to Property Owners → Add Owner.
2. Choose "Individual", enter a first and last name, email, and phone.
3. Save.
4. Open the new owner's detail page → Addresses tab → add a mailing address and mark it primary.
5. Go to Bank Accounts tab → add their bank details and mark primary.

**Expected Result:** The owner appears in the list with an auto-generated
code (e.g. `OWN-000003`). The address and bank account both show a
"Primary" badge. The Dashboard's "Missing Bank Details" count does not
include this owner anymore.
Pass ⬜ Fail ⬜

---

### UAT-2: Onboard a company property owner with multiple contacts
**Steps:**
1. Add Owner → choose "Company", enter a company name.
2. On the detail page, add two contacts: one "Finance Manager", one
   "Operations Manager". Mark the Finance Manager as primary.
3. Add the company's registered address.
4. Upload the company's trade license as a document (type: Trade License),
   with an expiry date 1 year from today.

**Expected Result:** Both contacts appear, only the Finance Manager shows
"Primary". The trade license document appears in the Documents tab and
does NOT show an "Expired" badge (future date).
Pass ⬜ Fail ⬜

---

### UAT-3: Catch an expiring document
**Steps:**
1. On any owner, upload a document with an expiry date set in the past
   (e.g. last month).

**Expected Result:** The document immediately shows a red "Expired" badge
next to it in the Documents tab, so staff can spot it at a glance.
Pass ⬜ Fail ⬜

---

### UAT-4: Only one primary contact point at a time
**Steps:**
1. On a company owner with 2+ addresses, mark a second address as
   "Primary".

**Expected Result:** The previously-primary address automatically loses
its "Primary" badge — the system never allows two primaries at once,
avoiding confusion about which address to use for correspondence.
Pass ⬜ Fail ⬜

---

### UAT-5: Find an owner quickly
**Steps:**
1. On the Owners list, type part of a company name, a phone number, and
   then a national ID into the search box (as three separate searches).
2. Use the "Type" filter to show only Companies.

**Expected Result:** Each search returns the matching owner(s) within a
second. The type filter narrows the list correctly.
Pass ⬜ Fail ⬜

---

### UAT-6: Track owner history
**Steps:**
1. Make a handful of changes to one owner: edit their phone number, add a
   bank account, upload a document.
2. Open the History tab.

**Expected Result:** Every change appears in plain English with a
timestamp, most recent first — a Branch Manager can see exactly what
happened to this owner's file without digging through raw data.
Pass ⬜ Fail ⬜

---

### UAT-7: Leave a note for a colleague
**Steps:**
1. On an owner's Notes tab, add a note like "Called owner — prefers email
   over phone."
2. Pin the note.

**Expected Result:** The note appears immediately and, once pinned, stays
at the top of the list even as new notes are added — useful context for
the next person who opens this owner's file.
Pass ⬜ Fail ⬜

---

### UAT-8: Role boundaries hold for owner data
**Steps:**
1. Log in as the seeded Staff user (`sam.staff@pms-demo.com`).
2. Navigate to Property Owners.
3. Open an owner's detail page.

**Expected Result:** Staff can view owners and their details but sees no
Add/Edit/Delete buttons anywhere on the page — view-only access, enforced
by the backend as well as hidden in the UI.
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

**Overall Phase 2 approval:** ⬜ Approved to proceed to Phase 3  ⬜ Changes requested
