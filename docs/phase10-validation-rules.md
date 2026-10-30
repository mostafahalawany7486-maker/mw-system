# Phase 10 — Accounting: Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Design Overview
Chart of Accounts is a self-referential tree: header/summary accounts
(`allow_posting=false`) exist purely for grouping and reporting; only leaf
accounts can receive journal entry lines. Journal Entry follows a strict
draft → posted → reversed lifecycle — a posted entry can never be edited
or deleted, only reversed (a new offsetting entry), preserving a complete
audit trail. General Ledger, Trial Balance, Balance Sheet, Income
Statement, and Cash Flow are computed live from posted journal entry
lines on every request — none of them are stored tables, so they can
never drift out of sync with the underlying ledger.

## Chart of Accounts
| Field | Rule |
|---|---|
| `account_code` | Required, unique, **user-defined** (not auto-generated like other entities in this system) — chart-of-accounts numbering is intentional business configuration, not an operational record |
| `account_type` | One of `asset`, `liability`, `equity`, `revenue`, `expense` |
| `parent_account_id` | Optional; if set, must reference an existing account with the **same** `account_type` (400 otherwise) |
| `allow_posting` | Defaults to `true`; set to `false` for header/summary accounts used only for grouping |
| Deletion | Blocked (409) if the account has child accounts, or has any journal entry lines ever posted to it |
| `normal_balance` | Computed, not stored: `debit` for asset/expense, `credit` for liability/equity/revenue |

## Cost Centers
| Rule |
|---|
| `cost_center_code` required, unique |
| Optionally linked to a `property_id` and/or `branch_id` for segmented reporting |

## VAT
| Rule |
|---|
| `rate_percentage` must be between 0 and 100 |
| **Simplification**: a single "VAT Control" GL account nets output and input VAT together, rather than tracking separate Payable/Receivable accounts — appropriate for a small-to-mid property management operation; documented here rather than silently assumed |
| The seeded default Posting Rules are deliberately **VAT-free** — Phase 8's transaction amounts were recorded without a tax-inclusive assumption, and applying VAT retroactively to the default mapping would silently change what those historical dollar amounts represent. VAT-aware rules can be added deliberately by attaching a `vat_rate_id` to a Posting Rule going forward |

## Automatic Posting
| Rule |
|---|
| A `PostingRule` maps a Phase 8 `transaction_type` (+ optional `category` for finer-grained expense/income mapping) to an "offset" GL account — the non-cash side of the entry |
| Exact `(transaction_type, category)` match is preferred; falls back to `(transaction_type, category=None)` if no exact match exists |
| Duplicate `(transaction_type, category)` combinations are rejected (409) |
| The offset account must have `allow_posting=true` (400 otherwise) |
| The cash/bank side of the entry is resolved from the transaction's own `FinancialAccount.gl_account_id` — a link exposed on `PUT /financial/accounts/{id}` |
| If no matching rule exists, or the account has no GL link, Automatic Posting **silently skips** — the underlying Phase 8 transaction still succeeds. An unmapped transaction type is not an error; it just doesn't have a journal entry yet |
| A Transfer posts **one** journal entry per transfer pair (not two), debiting the destination GL account and crediting the source |
| Deleting a Phase 8 transaction that has a **posted** journal entry linked to it is blocked (409) — reverse the journal entry first |

## Journal Entries
| Rule |
|---|
| Every entry needs at least 2 lines |
| Each line must have either a debit or a credit amount greater than 0 — never both, never neither (422 otherwise) |
| Total debits must equal total credits **at creation time** (validated by the schema before the entry ever reaches the database) |
| Every line's account must have `allow_posting=true` — checked both at creation and again at posting time |
| New entries start as `draft`; only `draft` entries can be edited or deleted |
| Posting re-validates the balance and posting-eligibility, then stamps `posted_at` |
| Only `posted` entries can be reversed; reversal creates a new `posted` entry with every line's debit/credit swapped, and marks the original `reversed` (never edited, never deleted) |

## Reports
| Report | Computation |
|---|---|
| Trial Balance | Sum of debits/credits per account, presented on its normal side, as of a given date — always balances by construction if every entry is balanced |
| General Ledger | Opening balance (all posted activity before the range) + each line's running delta = closing balance |
| Balance Sheet | Point-in-time snapshot as of a date: Assets vs. Liabilities + Equity |
| Income Statement | Period-based (date range only, no period-closing entries — a documented simplification): Revenue − Expenses = Net Income |
| Cash Flow | Simplified direct method: Phase 8 transactions grouped by `transaction_type` within the date range, excluding transfers (which don't change total cash) |
| VAT Report | Sums `vat_amount` from posted journal entry lines by VAT rate, split into output (credit-side) and input (debit-side) |
