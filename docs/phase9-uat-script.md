# Phase 9 — Maintenance: User Acceptance Testing (UAT) Script

---

### UAT-1: Report a maintenance issue
**Steps:**
1. Go to Maintenance → Report Issue.
2. Select a property, give it a title and description, choose a category and priority.
3. Save.

**Expected Result:** The request appears in the list with status "Reported"
and a system-generated request number (e.g. MNT-000004).
Pass ⬜ Fail ⬜

---

### UAT-2: Assign a contractor and technician
**Steps:**
1. Open the request from UAT-1, click Assign.
2. Choose a contractor and/or technician, optionally set a scheduled date.

**Expected Result:** The status moves to "Assigned," and the assigned
party's name shows on the request card and detail page.
Pass ⬜ Fail ⬜

---

### UAT-3: Start work and log materials + labor
**Steps:**
1. Click Start Work — status moves to "In Progress."
2. Go to the Materials & Labor tab, add a material (e.g. "Pipe fitting", qty 2, unit cost $10) and a labor entry (e.g. 2 hours at $45/hr).

**Expected Result:** Each line item shows its own computed total. The
Overview tab's "Actual Cost" reflects the sum of everything logged so far
— never a number you have to calculate or enter yourself.
Pass ⬜ Fail ⬜

---

### UAT-4: Upload before and after photos
**Steps:**
1. Go to the Before / After Photos tab.
2. Upload one photo tagged "Before" and one tagged "After," each with a short caption.

**Expected Result:** Photos appear in their respective sections
immediately, thumbnail-sized, with captions visible underneath.
Pass ⬜ Fail ⬜

---

### UAT-5: Put a request on hold and resume it
**Steps:**
1. On an in-progress request, click Hold and give a reason (e.g. "Waiting
   on replacement parts").
2. Later, click Resume.

**Expected Result:** The status moves to "On Hold" with the reason visible
on the Overview tab, then back to "In Progress" on resume.
Pass ⬜ Fail ⬜

---

### UAT-6: Complete a request
**Steps:**
1. Click Complete, confirm the completion date.

**Expected Result:** Status moves to "Completed." The request becomes
read-only (no more editing core fields), and the final actual cost is
locked in as the historical record.
Pass ⬜ Fail ⬜

---

### UAT-7: See overdue and urgent requests on the dashboard
**Steps:**
1. Go to the Maintenance dashboard.

**Expected Result:** Widgets clearly separate open work from what's
overdue (past its scheduled date) and what's urgent, so staff can
prioritize at a glance without reading every row.
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

**Overall Phase 9 approval:** ⬜ Approved to proceed to the next phase  ⬜ Changes requested
