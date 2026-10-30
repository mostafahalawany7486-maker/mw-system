# Phase 8 — Financial Management: Validation Rules

Adds to (does not replace) previous phases' validation-rules docs.

## Design Overview
Tenant Payments, Owner Payments, Expenses, Income, Deposits Received,
Deposit Refunds, and Refunds are all modeled as rows in a single
**Transaction** ledger table with a `transaction_type` discriminator,
rather than as separate tables — they share the same core shape (amount,
account, date, counterparty) and this keeps balance math and reporting
consistent. Transfers are the one exception: each transfer creates **two**
linked Transaction rows (`transfer_out` + `transfer_in`) so that
per-account balance calculation never needs special-casing.

## Financial Accounts (Cash & Bank)
| Field | Rule |
|---|---|
| `account_type` | Must be `cash` or `bank` |
| `bank_name` | Required when `account_type=bank` (422 otherwise) |
| `account_code` | System-generated (`ACC-000001` sequence), immutable |
| `current_balance` | **Never stored** — computed live as `opening_balance + sum(completed inflows) - sum(completed outflows)` for that account. This means it can never drift out of sync with the transaction history |
| Deletion | Blocked (409) unless `current_balance == 0` — prevents silently losing track of money by deleting an account that still holds a balance |

## Transactions
| Field | Rule |
|---|---|
| `transaction_type` | One of `tenant_payment`, `owner_payment`, `expense`, `income`, `deposit_received`, `deposit_refund`, `refund` (transfers use the dedicated `/financial/transfers` endpoint, not this one) |
| `amount` | Must be greater than 0 |
| `account_id` | Required, must reference an existing account (400 if invalid) |
| `tenant_id` | Required for `tenant_payment`, `deposit_received`, `deposit_refund`, `refund` (422 if missing) |
| `owner_id` | Required for `owner_payment` (422 if missing) |
| `direction` | Derived automatically from `transaction_type` — never client-settable. Inflow types: tenant_payment, income, deposit_received. Outflow types: owner_payment, expense, deposit_refund, refund |
| `transaction_number` | System-generated (`TXN-000001` sequence), immutable |
| Receipts | Auto-issued for `tenant_payment` and `owner_payment` only — the two transaction types that represent an actual payment being received or paid out. No manual "create receipt" action exists |
| Installment sync | If `rental_installment_id` or `lease_installment_id` is provided, that installment (Phase 7 or Phase 3) is automatically marked `paid` with the transaction's date, method, and reference — avoiding two disconnected sources of truth for "has this been paid" |

## Transfers
| Rule |
|---|
| `from_account_id` and `to_account_id` must be different (422 otherwise) |
| The transfer amount cannot exceed the source account's current balance (400 if it would overdraw) |
| Creates two Transaction rows atomically, cross-linked via `transfer_pair_id` on both sides |

## Invoices
| Field | Rule |
|---|---|
| `amount` | Must be greater than 0 |
| `due_date` | Cannot be before `issue_date` (422 otherwise) |
| `invoice_status` | `draft → sent → paid`, or `→ cancelled` at any point before paid. A paid invoice can never be cancelled (409) |
| Editing | Blocked (409) once an invoice is `paid` or `cancelled` |
| Send | Only from `draft` (409 otherwise) |
| Record Payment | Only from `sent` or `overdue` (409 otherwise). Internally creates a `tenant_payment` Transaction (with its own auto-issued Receipt) and links it via `paid_transaction_id` — so an invoice's payment history is always traceable back to a real ledger entry |
| Maintenance sweep | Any `sent` invoice past its `due_date` is automatically flagged `overdue` — idempotent, safe to run repeatedly |

## Outstanding Balance
| Rule |
|---|
| **Not a stored table.** Computed live by aggregating `pending`/`overdue` installments directly from Rental Payment Installments (tenant side, Phase 7) and Lease Payment Installments (owner side, Phase 3) |
| This guarantees Outstanding Balance can never go stale — marking an installment paid anywhere in the system (Phase 3/7 directly, or via a linked Phase 8 transaction) is immediately reflected |
| Only tenants/owners with a positive outstanding total appear in the results |

## Cross-cutting
- All monetary amounts use `Numeric(14, 2)` at the database level to avoid floating-point rounding errors.
- Every list/detail endpoint in this module follows the same soft-delete (`deleted_at`) pattern as prior phases — nothing is ever hard-deleted from the ledger.
