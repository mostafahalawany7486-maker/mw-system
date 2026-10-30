# Phase 10 — Accounting: User Acceptance Testing (UAT) Script

---

### UAT-1: Set up the chart of accounts and link a cash account
**Steps:**
1. Go to Accounting → Chart of Accounts. Confirm the seeded tree (Assets, Liabilities, Equity, Revenue, Expenses) displays with expandable header rows.
2. Go to Financial → Accounts, open your Petty Cash account, and confirm it shows a linked GL account.

**Expected Result:** The chart of accounts renders as a hierarchy. Cash and
Bank accounts are pre-linked to their GL ledger accounts from the sample
data.
Pass ⬜ Fail ⬜

---

### UAT-2: Record a transaction and watch it post automatically
**Steps:**
1. Go to Financial → Transactions → Record Transaction. Record a Tenant
   Payment against the Bank account.
2. Go to Accounting → Journal Entries.

**Expected Result:** A new journal entry appears automatically, already
Posted, with the payment amount balanced between the bank account (debit)
and Rental Income (credit) — no manual bookkeeping required.
Pass ⬜ Fail ⬜

---

### UAT-3: Enter and post a manual journal entry
**Steps:**
1. Go to Accounting → Journal Entries → New Entry.
2. Add two lines that don't balance (e.g. debit 100, credit 50) and try to
   save.
3. Fix the credit line to also read 100, save, then click Post.

**Expected Result:** The unbalanced attempt is blocked with a clear
"Not balanced" indicator before you can even save. Once balanced, it
saves as Draft, and posting moves it to Posted.
Pass ⬜ Fail ⬜

---

### UAT-4: Reverse a posted entry
**Steps:**
1. Open any Posted journal entry and click Reverse.

**Expected Result:** A brand-new entry appears with every debit and
credit swapped, and the original entry now shows status "Reversed" —
nothing was edited or deleted, preserving a full audit trail.
Pass ⬜ Fail ⬜

---

### UAT-5: Run the core financial reports
**Steps:**
1. Go to Accounting → Reports. Run Trial Balance, then Balance Sheet, then
   Income Statement for the current month.

**Expected Result:** Trial Balance shows "Balanced" with equal debit and
credit totals. Balance Sheet shows "Balanced" with Assets equal to
Liabilities plus Equity. Income Statement shows Revenue, Expenses, and a
computed Net Income.
Pass ⬜ Fail ⬜

---

### UAT-6: Check the VAT report
**Steps:**
1. Go to Accounting → Cost Centers & VAT and review the seeded VAT rates.
2. Go to Reports → VAT Report for the last 30 days.

**Expected Result:** The VAT report structure loads cleanly even with no
VAT-bearing transactions yet (the seeded posting rules are deliberately
VAT-free, to avoid silently reinterpreting historical amounts) — output,
input, and net VAT all show as zero rather than erroring.
Pass ⬜ Fail ⬜

---

### UAT-7: Try to delete a transaction that's already posted to the ledger
**Steps:**
1. Find a Financial transaction that has an auto-posted journal entry
   (e.g. one you created in UAT-2).
2. Try to delete it from Financial → Transactions.

**Expected Result:** The deletion is blocked with a message asking you to
reverse the journal entry first — protecting the integrity of the ledger.
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

**Overall Phase 10 approval:** ⬜ Approved to proceed to the next phase  ⬜ Changes requested
