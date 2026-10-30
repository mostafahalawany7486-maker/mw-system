# Phase 8 — Financial Management: User Acceptance Testing (UAT) Script

---

### UAT-1: Record rent received from a tenant
**Steps:**
1. Go to Financial → Transactions → Record Transaction.
2. Choose "Tenant Payment," select a tenant, an amount, and a bank account.
3. Save.

**Expected Result:** The transaction appears in the list with a green
"+" amount. A receipt is automatically generated — visible on the
Receipts tab — with no extra step required.
Pass ⬜ Fail ⬜

---

### UAT-2: Record an expense
**Steps:**
1. Record Transaction → "Expense," enter an amount, category (e.g.
   "maintenance"), and a cash account.

**Expected Result:** The transaction appears with a red "-" amount. No
receipt is generated for expenses — only tenant and owner payments issue
receipts.
Pass ⬜ Fail ⬜

---

### UAT-3: Transfer money from the bank account to petty cash
**Steps:**
1. On the Transactions tab, click Transfer.
2. Choose a source (bank) and destination (cash) account and an amount.

**Expected Result:** Both account balances update immediately —
the source account balance drops, the destination rises by the same
amount. Two linked transactions appear in the Transactions list.
Pass ⬜ Fail ⬜

---

### UAT-4: Bill a tenant and get paid
**Steps:**
1. Go to Financial → Invoices → Create Invoice, fill in a tenant, amount,
   and due date.
2. Click Send on the new draft invoice.
3. Click "Record Payment," choose the account the money lands in.

**Expected Result:** The invoice moves from Draft → Sent → Paid. A
matching transaction (and receipt) is created automatically behind the
scenes — you don't need to also manually record a separate payment.
Pass ⬜ Fail ⬜

---

### UAT-5: See who owes rent
**Steps:**
1. Go to Financial → Outstanding Balances.

**Expected Result:** Any tenant with unpaid or overdue rent installments
appears with their total amount owed, pulled live from the Rental
Contracts payment schedules — no manual syncing needed. Clicking a name
takes you to that tenant's profile.
Pass ⬜ Fail ⬜

---

### UAT-6: Check overall cash position
**Steps:**
1. Go to Financial → Overview (or the main Dashboard).

**Expected Result:** You can see total cash on hand, total in the bank,
this month's income and expenses, and both outstanding balances at a
glance — everything needed for a quick financial health check.
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

**Overall Phase 8 approval:** ⬜ Approved to proceed to the next phase  ⬜ Changes requested
