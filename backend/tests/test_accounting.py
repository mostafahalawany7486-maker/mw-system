"""
Accounting tests: Chart of Accounts, Cost Centers, VAT Rates, Posting
Rules, Journal Entry lifecycle (draft/post/reverse), Automatic Posting
from Phase 8 transactions, and every report (Trial Balance, General
Ledger, Balance Sheet, Income Statement, Cash Flow, VAT).
"""
from datetime import date, timedelta
from decimal import Decimal


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_account(client, headers, code, name, account_type, parent_id=None, allow_posting=True):
    payload = {"account_code": code, "account_name": name, "account_type": account_type, "allow_posting": allow_posting}
    if parent_id:
        payload["parent_account_id"] = parent_id
    resp = client.post("/api/v1/accounting/chart-of-accounts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup_basic_coa(client, headers):
    """Cash (asset), Revenue, Expense — enough for most tests."""
    cash = _create_account(client, headers, "1110", "Cash on Hand", "asset")
    bank = _create_account(client, headers, "1120", "Bank", "asset")
    revenue = _create_account(client, headers, "4100", "Test Revenue", "revenue")
    expense = _create_account(client, headers, "5100", "Test Expense", "expense")
    equity = _create_account(client, headers, "3100", "Retained Earnings", "equity")
    return {"cash": cash, "bank": bank, "revenue": revenue, "expense": expense, "equity": equity}


# ---------------- Chart of Accounts ----------------
def test_create_account(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_account(client, headers, "1110", "Cash on Hand", "asset")
    assert account["account_code"] == "1110"
    assert account["normal_balance"] == "debit"


def test_invalid_account_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "9999", "account_name": "Bad", "account_type": "bogus"}, headers=headers)
    assert resp.status_code == 422


def test_duplicate_account_code_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    _create_account(client, headers, "1110", "Cash on Hand", "asset")
    resp = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "1110", "account_name": "Dup", "account_type": "asset"}, headers=headers)
    assert resp.status_code == 409


def test_child_account_type_must_match_parent(client, seeded_admin):
    headers = _auth_headers(client)
    parent = _create_account(client, headers, "1000", "Assets", "asset", allow_posting=False)
    resp = client.post("/api/v1/accounting/chart-of-accounts", json={
        "account_code": "4999", "account_name": "Bad Child", "account_type": "revenue", "parent_account_id": parent["id"],
    }, headers=headers)
    assert resp.status_code == 400


def test_cannot_delete_account_with_children(client, seeded_admin):
    headers = _auth_headers(client)
    parent = _create_account(client, headers, "1000", "Assets", "asset", allow_posting=False)
    _create_account(client, headers, "1110", "Cash", "asset", parent_id=parent["id"])
    resp = client.delete(f"/api/v1/accounting/chart-of-accounts/{parent['id']}", headers=headers)
    assert resp.status_code == 409


# ---------------- Cost Centers ----------------
def test_create_cost_center(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/accounting/cost-centers", json={"cost_center_code": "CC-001", "name": "Test Cost Center"}, headers=headers)
    assert resp.status_code == 201


def test_duplicate_cost_center_code_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/accounting/cost-centers", json={"cost_center_code": "CC-001", "name": "First"}, headers=headers)
    resp = client.post("/api/v1/accounting/cost-centers", json={"cost_center_code": "CC-001", "name": "Second"}, headers=headers)
    assert resp.status_code == 409


# ---------------- VAT Rates ----------------
def test_create_vat_rate(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/accounting/vat-rates", json={"code": "STD5", "name": "Standard 5%", "rate_percentage": "5.00"}, headers=headers)
    assert resp.status_code == 201


def test_invalid_vat_rate_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/accounting/vat-rates", json={"code": "BAD", "name": "Bad Rate", "rate_percentage": "150"}, headers=headers)
    assert resp.status_code == 422


# ---------------- Posting Rules ----------------
def test_create_posting_rule(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    resp = client.post("/api/v1/accounting/posting-rules", json={
        "transaction_type": "tenant_payment", "offset_account_id": coa["revenue"]["id"],
    }, headers=headers)
    assert resp.status_code == 201


def test_duplicate_posting_rule_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "tenant_payment", "offset_account_id": coa["revenue"]["id"]}, headers=headers)
    resp = client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "tenant_payment", "offset_account_id": coa["expense"]["id"]}, headers=headers)
    assert resp.status_code == 409


def test_posting_rule_offset_must_allow_posting(client, seeded_admin):
    headers = _auth_headers(client)
    header_account = _create_account(client, headers, "4000", "Revenue Header", "revenue", allow_posting=False)
    resp = client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "income", "offset_account_id": header_account["id"]}, headers=headers)
    assert resp.status_code == 400


# ---------------- Journal Entries ----------------
def test_create_balanced_entry_is_draft(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    resp = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "description": "Test entry",
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "100.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "100.00"},
        ],
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["entry_status"] == "draft"
    assert body["entry_number"].startswith("JE-")


def test_create_unbalanced_entry_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    resp = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "100.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "50.00"},
        ],
    }, headers=headers)
    assert resp.status_code == 422


def test_line_cannot_have_both_debit_and_credit(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    resp = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "100.00", "credit_amount": "100.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "100.00"},
        ],
    }, headers=headers)
    assert resp.status_code == 422


def test_entry_needs_at_least_two_lines(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    resp = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [{"account_id": coa["cash"]["id"], "debit_amount": "100.00"}],
    }, headers=headers)
    assert resp.status_code == 422


def test_cannot_post_to_header_account(client, seeded_admin):
    headers = _auth_headers(client)
    header_account = _create_account(client, headers, "1000", "Assets Header", "asset", allow_posting=False)
    coa = _setup_basic_coa(client, headers)
    resp = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": header_account["id"], "debit_amount": "100.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "100.00"},
        ],
    }, headers=headers)
    assert resp.status_code == 400


def test_post_and_reverse_entry(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "200.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "200.00"},
        ],
    }, headers=headers).json()

    posted = client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)
    assert posted.status_code == 200
    assert posted.json()["entry_status"] == "posted"

    # Posting again should fail
    resp = client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)
    assert resp.status_code == 409

    # Cannot delete a posted entry
    del_resp = client.delete(f"/api/v1/accounting/journal-entries/{entry['id']}", headers=headers)
    assert del_resp.status_code == 409

    # Reverse it
    reversal = client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/reverse", params={"reversal_date": str(date.today())}, headers=headers)
    assert reversal.status_code == 200
    reversal_body = reversal.json()
    assert reversal_body["entry_status"] == "posted"
    assert reversal_body["description"].startswith("Reversal of")

    original = client.get(f"/api/v1/accounting/journal-entries/{entry['id']}", headers=headers).json()
    assert original["entry_status"] == "reversed"


def test_cannot_reverse_draft_entry(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "50.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "50.00"},
        ],
    }, headers=headers).json()
    resp = client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/reverse", params={"reversal_date": str(date.today())}, headers=headers)
    assert resp.status_code == 409


def test_can_delete_draft_entry(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "50.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "50.00"},
        ],
    }, headers=headers).json()
    resp = client.delete(f"/api/v1/accounting/journal-entries/{entry['id']}", headers=headers)
    assert resp.status_code == 200


# ---------------- Automatic Posting ----------------
def test_automatic_posting_from_income_transaction(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)

    fin_account = client.post("/api/v1/financial/accounts", json={
        "account_type": "bank", "name": "AutoPost Bank", "bank_name": "Test Bank", "opening_balance": "0",
    }, headers=headers).json()
    linked = client.put(f"/api/v1/financial/accounts/{fin_account['id']}", json={"gl_account_id": coa["bank"]["id"]}, headers=headers)
    assert linked.status_code == 200
    assert linked.json()["gl_account_id"] == coa["bank"]["id"]

    client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "income", "offset_account_id": coa["revenue"]["id"]}, headers=headers)

    txn = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "500.00", "account_id": fin_account["id"],
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert txn.status_code == 201

    entries = client.get("/api/v1/accounting/journal-entries", params={"source_type": "system"}, headers=headers).json()
    assert entries["total"] == 1
    entry = entries["items"][0]
    assert entry["source_transaction_id"] == txn.json()["id"]
    assert Decimal(entry["total_debit"]) == Decimal("500.00")
    assert Decimal(entry["total_credit"]) == Decimal("500.00")


def test_no_automatic_posting_without_gl_link(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "income", "offset_account_id": coa["revenue"]["id"]}, headers=headers)

    fin_account = client.post("/api/v1/financial/accounts", json={
        "account_type": "cash", "name": "Unlinked Cash", "opening_balance": "0",
    }, headers=headers).json()
    txn = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "200.00", "account_id": fin_account["id"],
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert txn.status_code == 201  # underlying transaction still succeeds

    entries = client.get("/api/v1/accounting/journal-entries", params={"source_type": "system"}, headers=headers).json()
    assert entries["total"] == 0


def test_deleting_transaction_with_posted_entry_is_blocked(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    fin_account = client.post("/api/v1/financial/accounts", json={
        "account_type": "bank", "name": "AutoPost Bank 2", "bank_name": "Test Bank", "opening_balance": "0",
    }, headers=headers).json()
    client.put(f"/api/v1/financial/accounts/{fin_account['id']}", json={"gl_account_id": coa["bank"]["id"]}, headers=headers)
    client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "income", "offset_account_id": coa["revenue"]["id"]}, headers=headers)

    txn = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "100.00", "account_id": fin_account["id"],
        "transaction_date": str(date.today()),
    }, headers=headers).json()

    resp = client.delete(f"/api/v1/financial/transactions/{txn['id']}", headers=headers)
    assert resp.status_code == 409


# ---------------- Reports ----------------
def test_trial_balance_is_balanced_after_posting(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "1000.00"},
            {"account_id": coa["equity"]["id"], "credit_amount": "1000.00"},
        ],
    }, headers=headers).json()
    client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)

    resp = client.get("/api/v1/accounting/reports/trial-balance", params={"as_of_date": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_balanced"] is True
    assert Decimal(body["total_debit"]) == Decimal(body["total_credit"])


def test_balance_sheet_balances(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "5000.00"},
            {"account_id": coa["equity"]["id"], "credit_amount": "5000.00"},
        ],
    }, headers=headers).json()
    client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)

    resp = client.get("/api/v1/accounting/reports/balance-sheet", params={"as_of_date": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_balanced"] is True
    assert Decimal(body["total_assets"]) == Decimal(body["total_liabilities"]) + Decimal(body["total_equity"])


def test_income_statement_computes_net_income(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "800.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "800.00"},
        ],
    }, headers=headers).json()
    client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)
    entry2 = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["expense"]["id"], "debit_amount": "300.00"},
            {"account_id": coa["cash"]["id"], "credit_amount": "300.00"},
        ],
    }, headers=headers).json()
    client.post(f"/api/v1/accounting/journal-entries/{entry2['id']}/post", headers=headers)

    resp = client.get("/api/v1/accounting/reports/income-statement", params={
        "date_from": str(date.today() - timedelta(days=1)), "date_to": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["net_income"]) == Decimal("500.00")


def test_general_ledger_running_balance(client, seeded_admin):
    headers = _auth_headers(client)
    coa = _setup_basic_coa(client, headers)
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": coa["cash"]["id"], "debit_amount": "150.00"},
            {"account_id": coa["revenue"]["id"], "credit_amount": "150.00"},
        ],
    }, headers=headers).json()
    client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)

    resp = client.get("/api/v1/accounting/reports/general-ledger", params={"account_id": coa["cash"]["id"]}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["closing_balance"]) == Decimal("150.00")
    assert len(body["lines"]) == 1


def test_vat_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/accounting/reports/vat", params={
        "date_from": str(date.today() - timedelta(days=30)), "date_to": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_output_vat" in body and "total_input_vat" in body


def test_cash_flow_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/accounting/reports/cash-flow", params={
        "date_from": str(date.today() - timedelta(days=30)), "date_to": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "net_change_in_cash" in body


def test_accounting_requires_authentication(client, seeded_admin):
    resp = client.get("/api/v1/accounting/chart-of-accounts")
    assert resp.status_code == 401
