"""
Financial Management tests: accounts, transactions (with installment sync
and auto-receipts), transfers, invoices, outstanding balances.
"""
from datetime import date, timedelta


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_cash_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "cash", "name": "Test Cash Drawer", "opening_balance": "1000.00"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_bank_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={
        "account_type": "bank", "name": "Test Bank Account", "bank_name": "Test Bank", "opening_balance": "5000.00",
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_tenant(client, headers):
    resp = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Finance", "last_name": "Tenant"}, headers=headers)
    return resp.json()["id"]


def _create_owner(client, headers):
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Finance", "last_name": "Owner"}, headers=headers)
    return resp.json()["id"]


# ---------------- Accounts ----------------
def test_create_cash_account(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "cash", "name": "Front Desk Cash", "opening_balance": "500.00"}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_code"].startswith("ACC-")
    assert body["current_balance"] == "500.00"


def test_bank_account_requires_bank_name(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "No Bank Name"}, headers=headers)
    assert resp.status_code == 422


def test_invalid_account_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "crypto", "name": "Bad Type"}, headers=headers)
    assert resp.status_code == 422


def test_cannot_delete_account_with_balance(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_cash_account(client, headers)
    resp = client.delete(f"/api/v1/financial/accounts/{account_id}", headers=headers)
    assert resp.status_code == 409


# ---------------- Transactions ----------------
def test_create_expense_transaction(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_cash_account(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "expense", "amount": "200.00", "account_id": account_id,
        "category": "utilities", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["direction"] == "out"
    assert body["transaction_number"].startswith("TXN-")
    assert body["receipt_number"] is None  # expenses don't auto-issue receipts


def test_tenant_payment_requires_tenant_id(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_cash_account(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "tenant_payment", "amount": "100.00", "account_id": account_id,
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 422


def test_tenant_payment_creates_receipt(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_bank_account(client, headers)
    tenant_id = _create_tenant(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "tenant_payment", "amount": "1200.00", "account_id": account_id,
        "tenant_id": tenant_id, "payment_method": "bank_transfer", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["direction"] == "in"
    assert body["receipt_number"] is not None
    assert body["receipt_number"].startswith("RCP-")


def test_owner_payment_requires_owner_id(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_bank_account(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "owner_payment", "amount": "100.00", "account_id": account_id,
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 422


def test_negative_amount_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_cash_account(client, headers)
    resp = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "expense", "amount": "-50.00", "account_id": account_id,
        "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 422


def test_account_balance_updates_with_transactions(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_cash_account(client, headers)  # opening 1000
    client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "300.00", "account_id": account_id, "transaction_date": str(date.today()),
    }, headers=headers)
    client.post("/api/v1/financial/transactions", json={
        "transaction_type": "expense", "amount": "150.00", "account_id": account_id, "transaction_date": str(date.today()),
    }, headers=headers)
    resp = client.get(f"/api/v1/financial/accounts/{account_id}", headers=headers)
    assert resp.json()["current_balance"] == "1150.00"


# ---------------- Transfers ----------------
def test_create_transfer(client, seeded_admin):
    headers = _auth_headers(client)
    bank_id = _create_bank_account(client, headers)  # opening 5000
    cash_id = _create_cash_account(client, headers)  # opening 1000
    resp = client.post("/api/v1/financial/transfers", json={
        "from_account_id": bank_id, "to_account_id": cash_id, "amount": "500.00", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["out_transaction"]["transaction_type"] == "transfer_out"
    assert body["in_transaction"]["transaction_type"] == "transfer_in"
    assert body["out_transaction"]["transfer_pair_id"] == body["in_transaction"]["id"]

    bank_balance = client.get(f"/api/v1/financial/accounts/{bank_id}", headers=headers).json()["current_balance"]
    cash_balance = client.get(f"/api/v1/financial/accounts/{cash_id}", headers=headers).json()["current_balance"]
    assert bank_balance == "4500.00"
    assert cash_balance == "1500.00"


def test_transfer_insufficient_balance_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    cash_id = _create_cash_account(client, headers)  # opening 1000
    bank_id = _create_bank_account(client, headers)
    resp = client.post("/api/v1/financial/transfers", json={
        "from_account_id": cash_id, "to_account_id": bank_id, "amount": "999999.00", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 400


def test_transfer_same_account_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    account_id = _create_cash_account(client, headers)
    resp = client.post("/api/v1/financial/transfers", json={
        "from_account_id": account_id, "to_account_id": account_id, "amount": "100.00", "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 422


# ---------------- Invoices ----------------
def test_create_and_send_invoice(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    resp = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "1500.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers)
    assert resp.status_code == 201
    invoice = resp.json()
    assert invoice["invoice_status"] == "draft"

    sent = client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)
    assert sent.status_code == 200
    assert sent.json()["invoice_status"] == "sent"


def test_record_invoice_payment(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_bank_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "800.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=10)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "transaction_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["invoice_status"] == "paid"
    assert resp.json()["paid_transaction_id"] is not None


def test_invoice_due_date_before_issue_date_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    resp = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "100.00", "issue_date": str(date.today()), "due_date": str(date.today() - timedelta(days=5)),
    }, headers=headers)
    assert resp.status_code == 422


def test_cannot_cancel_paid_invoice(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    account_id = _create_bank_account(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "300.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=5)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/record-payment", json={
        "account_id": account_id, "transaction_date": str(date.today()),
    }, headers=headers)
    resp = client.post(f"/api/v1/financial/invoices/{invoice['id']}/cancel", headers=headers)
    assert resp.status_code == 409


# ---------------- Outstanding Balances & Dashboard ----------------
def test_outstanding_balances_endpoint(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/financial/outstanding-balances", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "tenants" in body and "owners" in body


def test_financial_dashboard(client, seeded_admin):
    headers = _auth_headers(client)
    _create_cash_account(client, headers)
    resp = client.get("/api/v1/financial/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_cash_balance" in body
    assert "total_bank_balance" in body


def test_financial_requires_authentication(client, seeded_admin):
    resp = client.get("/api/v1/financial/accounts")
    assert resp.status_code == 401


def test_maintenance_sweep_marks_overdue_invoices(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    invoice = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "amount": "100.00", "issue_date": str(date.today() - timedelta(days=20)),
        "due_date": str(date.today() - timedelta(days=5)),
    }, headers=headers).json()
    client.post(f"/api/v1/financial/invoices/{invoice['id']}/send", headers=headers)

    resp = client.post("/api/v1/financial/maintenance/run", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["invoices_marked_overdue"] >= 1

    updated = client.get(f"/api/v1/financial/invoices/{invoice['id']}", headers=headers).json()
    assert updated["invoice_status"] == "overdue"
