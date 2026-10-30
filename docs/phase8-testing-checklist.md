# Phase 8 — Financial Management: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–7 running with migrations through `0008`. Run
`python seed.py` to load 2 accounts, 6 transactions, 2 receipts, and 1
draft invoice.

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0008_financial_management` without error
- [ ] Tables `financial_accounts`, `transactions`, `receipts`, `invoices` exist with all mandatory audit columns
- [ ] `python seed.py` registers the `financial` permission module, assigned to Administrator (all), Branch Manager (view/create/edit), Staff (view)
- [ ] Seed creates ACC-000001 (Petty Cash, $2,000 opening) and ACC-000002 (Main Operating Account, $50,000 opening)
- [ ] Seed creates 6 sample transactions including a tenant payment (with auto-issued receipt), an owner payment (with auto-issued receipt), an expense, income, and a linked transfer pair
- [ ] Seed creates INV-000001, a draft invoice for Laura Martinez

## 2. Financial Accounts (Cash & Bank)
- [ ] Create a Cash account → succeeds, `account_code` auto-generated (`ACC-000003`)
- [ ] Create a Bank account without `bank_name` → 422
- [ ] Invalid `account_type` (not cash/bank) → 422
- [ ] `current_balance` on a fresh account equals its `opening_balance`
- [ ] Deleting an account with a non-zero balance → 409 (must transfer funds out first)
- [ ] Deleting an account with a zero balance → succeeds

## 3. Transactions — Tenant & Owner Payments
- [ ] Record a `tenant_payment` with a valid `tenant_id` → succeeds, direction=`in`, a Receipt is auto-issued
- [ ] Record a `tenant_payment` without `tenant_id` → 422
- [ ] Record an `owner_payment` with a valid `owner_id` → succeeds, direction=`out`, a Receipt is auto-issued
- [ ] Record an `owner_payment` without `owner_id` → 422
- [ ] Linking a `tenant_payment` to a `rental_installment_id` marks that Rental Payment Installment (Phase 7) as `paid` — confirmed by checking the installment via `/rentals/{id}` afterward
- [ ] Linking an `owner_payment` to a `lease_installment_id` marks that Lease Payment Installment (Phase 3) as `paid`

## 4. Transactions — Expenses & Income
- [ ] Record an `expense` with a `category` (e.g. "maintenance") → succeeds, direction=`out`, **no** receipt auto-issued
- [ ] Record `income` with a `category` (e.g. "parking_fee") → succeeds, direction=`in`, no receipt

## 5. Transactions — Deposits & Refunds
- [ ] Record `deposit_received` for a tenant → succeeds, direction=`in`
- [ ] Record `deposit_refund` for a tenant → succeeds, direction=`out`
- [ ] Record `refund` for a tenant → succeeds, direction=`out`
- [ ] All three require `tenant_id` (422 if missing)

## 6. Transaction Validation
- [ ] `amount` ≤ 0 → 422 on every transaction type
- [ ] Invalid `account_id` → 400
- [ ] Invalid `payment_method` value → 422
- [ ] Cancelling a transaction (`transaction_status=cancelled`) excludes it from account balance calculations going forward

## 7. Account Balances
- [ ] After recording an inflow and an outflow on the same account, `current_balance = opening_balance + inflow - outflow`
- [ ] Balances are computed live (not stored) — confirmed by checking balance updates immediately after each new transaction with no separate "recalculate" step

## 8. Transfers
- [ ] Transfer between two accounts creates **two** linked Transaction rows (`transfer_out` + `transfer_in`), joined by `transfer_pair_id` in both directions
- [ ] Source account balance decreases by the transfer amount; destination account balance increases by the same amount
- [ ] Transfer exceeding the source account's current balance → 400 (insufficient balance)
- [ ] Transfer with `from_account_id == to_account_id` → 422

## 9. Receipts
- [ ] Every `tenant_payment` and `owner_payment` transaction has exactly one auto-issued Receipt, numbered sequentially (`RCP-000001`, ...)
- [ ] Receipts list/detail views show the linked transaction's amount, date, and counterparty
- [ ] No manual "create receipt" endpoint exists — receipts are strictly a byproduct of qualifying transactions (by design)

## 10. Invoices
- [ ] Create an invoice for a tenant → succeeds as `draft`, `invoice_number` auto-generated
- [ ] `due_date` before `issue_date` → 422
- [ ] Send a draft invoice → status becomes `sent`
- [ ] Sending a non-draft invoice → 409
- [ ] Record payment on a `sent`/`overdue` invoice → creates a `tenant_payment` Transaction (with auto-issued Receipt), invoice status becomes `paid`, `paid_transaction_id` is set
- [ ] Recording payment on a `draft`, `paid`, or `cancelled` invoice → 409
- [ ] Cancel a `sent` invoice → succeeds
- [ ] Cancel a `paid` invoice → 409
- [ ] Editing a `paid` or `cancelled` invoice's core fields → 409

## 11. Maintenance Sweep
- [ ] Running `/financial/maintenance/run` marks any `sent` invoice past its `due_date` as `overdue`
- [ ] Running it twice does not cause errors or duplicate side effects

## 12. Outstanding Balance
- [ ] `/financial/outstanding-balances` returns per-tenant totals computed live from Rental Payment Installments (Phase 7) with `pending`/`overdue` status
- [ ] Returns per-owner totals computed live from Lease Payment Installments (Phase 3) with `pending`/`overdue` status
- [ ] A tenant/owner with zero outstanding installments does not appear in the list
- [ ] Marking an installment paid (either directly in Phase 7/3, or via a linked Phase 8 transaction) immediately removes it from Outstanding Balance — no caching lag

## 13. Dashboard
- [ ] `/financial/dashboard/summary` shows correct total cash balance, total bank balance, this month's income and expense totals, and both outstanding totals
- [ ] Main Phase 1 Dashboard also shows a combined "Cash + Bank Balance" widget matching the sum shown on the Financial dashboard

## 14. Permissions
- [ ] Staff (view-only) can browse all financial data but sees no Add/Edit/Delete/Transfer/Send/Cancel/Record Payment controls
- [ ] Branch Manager can fully manage day-to-day financial operations (create/edit transactions, invoices, transfers) but cannot delete accounts or transactions (no `financial.delete` in the seeded role)

## 15. Automated tests
- [ ] `pytest backend/tests/test_financial.py` passes all cases (accounts, transactions of every type, transfers, invoices, outstanding balances, dashboard, permissions, maintenance sweep)
