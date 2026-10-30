# Phase 3 — Lease Agreements: User Acceptance Testing (UAT) Script

---

### UAT-1: Draft a new lease with an owner
**Steps:**
1. Go to Lease Agreements → Add Lease.
2. Select an existing owner, enter a property description, start/end dates,
   monthly rent, and a security deposit.
3. Save.

**Expected Result:** The lease appears in the list with an auto-generated
contract number (e.g. `LSE-000003`) and status "Draft" — nothing is
committed to as "in effect" yet, matching how real contracts move from
negotiation to signed.
Pass ⬜ Fail ⬜

---

### UAT-2: Activate a signed lease and generate its payment schedule
**Steps:**
1. Open the draft lease from UAT-1, click "Activate".
2. Go to the Payment Schedule tab → "Auto-Generate".

**Expected Result:** Status changes to "Active". The schedule fills in with
one installment per month (or per the chosen frequency) for the full lease
term, each showing "Pending".
Pass ⬜ Fail ⬜

---

### UAT-3: Record a rent payment
**Steps:**
1. On the Payment Schedule tab, find the first installment, click "Mark
   Paid".

**Expected Result:** That installment's status flips to "Paid" with
today's date recorded. The lease's "Outstanding Payments" total on the
Leases dashboard decreases accordingly.
Pass ⬜ Fail ⬜

---

### UAT-4: Terminate a lease early
**Steps:**
1. On an active lease, click "Terminate".
2. Enter a termination date and reason (e.g. "Owner sold the property").

**Expected Result:** Status changes to "Terminated", the reason is visible
on the Overview tab, and the lease can no longer be edited or have its
schedule modified — its record is now historical.
Pass ⬜ Fail ⬜

---

### UAT-5: Renew an expiring lease
**Steps:**
1. Find an active lease. Click "Renew".
2. Enter a new end date (and optionally an adjusted rent amount).

**Expected Result:** A brand-new lease is created with a new contract
number, linked back to the original. The original lease's status becomes
"Renewed" — its full payment history stays intact and separate from the
new contract's schedule.
Pass ⬜ Fail ⬜

---

### UAT-6: Get warned before a lease lapses
**Steps:**
1. Note a lease's `renewal_notice_days` setting (e.g. 30).
2. As an Administrator, click "Check Renewals" on the Leases page (this
   simulates the daily automated check).

**Expected Result:** Any active lease within its renewal window appears in
the "Leases needing renewal attention" banner, and an in-app notification
appears for the Administrator — so nobody is caught off guard by an
expiring contract.
Pass ⬜ Fail ⬜

---

### UAT-7: Track everything that happened to a contract
**Steps:**
1. On any lease that's been activated, had payments recorded, and
   possibly renewed, open the History tab.

**Expected Result:** A complete, plain-English timeline: created →
activated → installment paid → renewed (or terminated), each with a
timestamp — a manager can reconstruct the contract's full story without
asking anyone.
Pass ⬜ Fail ⬜

---

### UAT-8: Role boundaries hold for lease data
**Steps:**
1. Log in as the seeded Staff user.
2. Open Lease Agreements.

**Expected Result:** Staff can view leases and their payment schedules but
sees no Add/Activate/Terminate/Renew/Delete controls anywhere — enforced
both in the UI and by the API directly.
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

**Overall Phase 3 approval:** ⬜ Approved to proceed to Phase 4  ⬜ Changes requested
