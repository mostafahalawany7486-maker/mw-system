# Phase 10 — Accounting: Testing Checklist

Legend: [ ] not tested · [x] pass · [!] fail (log in Bug Checklist)

Prerequisite: Phases 1–9 running with migrations through `0010`. Run
`python seed.py` to load a 15-account chart of accounts, 2 cost centers,
2 VAT rates, 8 posting rules, and 4 journal entries (3 posted incl. an
opening-balances entry, 1 draft).

## 1. Migrations & Seed
- [ ] `alembic upgrade head` applies `0010_accounting` without error, including the additive `gl_account_id` column on `financial_accounts`
- [ ] Tables `chart_of_accounts`, `cost_centers`, `vat_rates`, `posting_rules`, `journal_entries`, `journal_entry_lines` all exist with mandatory audit columns
- [ ] `python seed.py` registers the `accounting` module — Administrator (all), Branch Manager (`accounting.view` only — GL access is accounting-staff territory, not general branch operations), Staff (no accounting access at all)
- [ ] Seed creates the full chart: 1000 Assets → 1100 Current Assets → 1110 Cash on Hand / 1120 Bank, 2000 Liabilities → 2100 Current Liabilities → 2110 Security Deposits Held / 2200 VAT Control, 3000 Equity → 3100 Retained Earnings, 4000 Revenue → 4100 Rental Income / 4200 Other Income, 5000 Expenses → 5100–5900
- [ ] ACC-000001 (Petty Cash) and ACC-000002 (Main Operating Account) from Phase 8 are linked to GL accounts 1110/1120 via `gl_account_id`
- [ ] JE-000001 "Opening balances" is posted and matches the Phase 8 opening balances ($2,000 cash + $50,000 bank = $52,000 retained earnings)
- [ ] JE-000002/JE-000003 demonstrate what Automatic Posting produces for TXN-000001 (tenant payment) and TXN-000002 (owner payment)
- [ ] JE-000004 is a draft entry, useful for testing the post/delete-draft workflow

## 2. Chart of Accounts
- [ ] Create an account — succeeds; account_code is user-defined (not auto-generated, since COA numbering is intentional business configuration)
- [ ] Duplicate `account_code` → 409
- [ ] Invalid `account_type` → 422
- [ ] A child account's `account_type` must match its parent's → 400 otherwise
- [ ] `allow_posting=false` marks a header/summary account (e.g. "1000 Assets") — these cannot receive journal entry lines
- [ ] Deleting an account with child accounts → 409
- [ ] Deleting an account with journal entry lines posted to it → 409
- [ ] GET with `with_balances=true` returns each account's live balance (normal-side net of posted activity)

## 3. Cost Centers
- [ ] Create a cost center, optionally linked to a Property → succeeds
- [ ] Duplicate `cost_center_code` → 409

## 4. VAT
- [ ] Create a VAT rate (0–100%) — a single "VAT Control" GL account nets payable/receivable rather than tracking them separately (documented simplification)
- [ ] Rate outside 0–100 → 422
- [ ] VAT Report for a date range returns output VAT (credit-side), input VAT (debit-side), and net VAT per rate, computed from posted journal entry lines' `vat_amount`

## 5. Automatic Posting
- [ ] **Posting Rules** map a Phase 8 transaction type (+ optional category) to a GL offset account; duplicate (type, category) → 409; offset account must have `allow_posting=true` → 400 otherwise
- [ ] Linking a Phase 8 `FinancialAccount` to a GL account via `gl_account_id` (now exposed on `PUT /financial/accounts/{id}`) is required before Automatic Posting can fire for that account
- [ ] Creating a Financial transaction (tenant_payment, owner_payment, expense, income, deposit_received, deposit_refund, refund) with both a matching Posting Rule AND a GL-linked account → automatically creates a **posted**, balanced Journal Entry (`source_type=system`, `source_transaction_id` set)
- [ ] Creating a transaction with **no matching Posting Rule** → transaction still succeeds, silently no journal entry is created (not an error)
- [ ] Creating a transaction on an account with **no `gl_account_id` linked** → transaction still succeeds, silently no journal entry is created
- [ ] A Transfer between two GL-linked accounts auto-posts exactly **one** journal entry (not two) — debits the destination GL account, credits the source
- [ ] Deleting a Phase 8 transaction that has a posted journal entry linked to it → 409 ("reverse the journal entry first")

## 6. Journal Entries
- [ ] Create a balanced entry (≥2 lines, total debits == total credits) → succeeds as `draft`
- [ ] Unbalanced entry → 422 (validated before it ever reaches the database)
- [ ] A line with both a debit and a credit amount → 422; a line with neither → 422
- [ ] Fewer than 2 lines → 422
- [ ] Posting to a header/summary account (`allow_posting=false`) → 400 at creation, and re-checked again at post time
- [ ] Post a draft entry → `posted`, `posted_at` stamped; posting an already-posted entry → 409
- [ ] Only draft entries can be edited or deleted; a posted entry → 409 on both
- [ ] Reverse a posted entry → creates a brand-new entry with every line's debit/credit swapped, marks the original `reversed` and links `reversed_entry_id`
- [ ] Reversing a draft entry → 409 (only posted entries can be reversed)

## 7. General Ledger
- [ ] For a given account and date range, returns each posted line with a running balance that correctly accounts for the account's normal side (debit-normal vs credit-normal)
- [ ] `opening_balance` reflects all posted activity before `date_from`; `closing_balance` equals `opening_balance` + all line deltas

## 8. Trial Balance
- [ ] As of any date, every account's net posted activity nets to zero across the whole ledger — `total_debit == total_credit`, `is_balanced: true`
- [ ] Only accounts with posted activity (nonzero net) appear in the line list

## 9. Balance Sheet
- [ ] As of any date, `total_assets == total_liabilities + total_equity` (`is_balanced: true`) whenever the underlying journal entries are balanced — this should be true automatically as a consequence of double-entry bookkeeping, not a separately-enforced rule
- [ ] Accounts with a zero balance in the period are omitted from each section

## 10. Income Statement
- [ ] For a date range, `net_income = total_revenue - total_expenses`, computed only from journal entries within that range (revenue/expense accounts are period accounts — no period-closing entries exist yet, a documented simplification)

## 11. Cash Flow
- [ ] For a date range, operating activities are grouped by Phase 8 `transaction_type` (transfers excluded, since they don't change total cash)
- [ ] `net_change_in_cash == closing_cash_balance - opening_cash_balance`, both computed independently from Phase 8's transaction history

## 12. Permissions
- [ ] Staff has no accounting access at all (403/permission-denied on every accounting endpoint) — deliberate, since GL/ledger access is typically restricted
- [ ] Branch Manager can view all accounting data and reports but cannot create/edit/delete (view-only)
- [ ] Administrator has full access including posting, reversing, and deleting draft entries

## 13. Automated tests
- [ ] `pytest backend/tests/test_accounting.py` passes all cases (chart of accounts incl. parent/child type matching and deletion guards, cost centers, VAT rates, posting rules incl. duplicate/posting-eligibility checks, full journal entry lifecycle incl. balance validation/posting/reversal, automatic posting incl. the silent-skip cases and the transaction-deletion safety check, and all six reports)
