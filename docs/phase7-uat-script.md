# Phase 7 — Rental Contracts (Company → Tenant): User Acceptance Testing (UAT) Script

---

### UAT-1: Sublease a unit to a tenant, with a discount
**Steps:**
1. Go to Rental Contracts → Add Contract.
2. Select a tenant and a property, set dates and rent amount.
3. Set Discount Type to "Fixed Amount" with a value and reason.
4. Save, then Activate the contract.

**Expected Result:** The contract appears as Active. The property's
availability now shows "Leased." The tenant and property are both clearly
linked on the contract's Overview tab.
Pass ⬜ Fail ⬜

---

### UAT-2: Generate a payment schedule with tax applied
**Steps:**
1. On the contract from UAT-1, set a Tax Rate (e.g. 5%).
2. Go to the Payment Schedule tab and click Auto-Generate.

**Expected Result:** Installments are created at the correct frequency,
each showing the rent amount, the discount subtracted, tax added on the
post-discount amount, and a running total.
Pass ⬜ Fail ⬜

---

### UAT-3: See a late fee applied automatically
**Steps:**
1. On a contract with a short grace period, add an installment with a due
   date a few days in the past.
2. Click "Check Renewals" (the maintenance sweep) on the Rental Contracts
   list page.

**Expected Result:** The installment now shows "Overdue" status, and — if
past the grace period — a late fee amount appears, correctly added to the
total.
Pass ⬜ Fail ⬜

---

### UAT-4: Mark rent as paid
**Steps:**
1. On any pending or overdue installment, click "Mark Paid."

**Expected Result:** The installment's status updates to "Paid"
immediately, and the action appears in the contract's History tab.
Pass ⬜ Fail ⬜

---

### UAT-5: Renew an expiring contract
**Steps:**
1. Open an active contract nearing its end date (or manually renew any
   active contract).
2. Click Renew, set a new end date.

**Expected Result:** A brand-new contract is created with a new contract
number, carrying over the same tenant, property, discount, tax, and late
fee settings. The old contract shows status "Renewed" and is no longer
editable.
Pass ⬜ Fail ⬜

---

### UAT-6: Terminate a contract early
**Steps:**
1. On an active contract, click Terminate, enter a date and reason.

**Expected Result:** The contract status updates to "Terminated" with the
reason visible on the Overview tab. The property's availability flips
back to "Available," ready to be leased again.
Pass ⬜ Fail ⬜

---

### UAT-7: See a blacklist warning without being blocked
**Steps:**
1. Start creating a new rental contract and select a tenant known to be
   blacklisted (e.g. the seeded Derek Voss).

**Expected Result:** A clear warning appears in the form, but you can
still proceed and create the contract — the system informs, it doesn't
block, leaving the business decision to staff.
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

**Overall Phase 7 approval:** ⬜ Approved to proceed to the next phase  ⬜ Changes requested
