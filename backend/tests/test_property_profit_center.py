"""
Property Profit Center tests: every financial transaction, invoice, and
journal entry line should resolve to a Property, and the 7 new
property-scoped reports should return correct, honestly-scoped data.
These tests also double as regression checks — every extended method
(income_statement, cash_flow, expense_report, profit_report,
dashboard_analytics, amount_by_property, section_balances) must still
work identically for its original portfolio-wide callers.
"""
from datetime import date, timedelta
from decimal import Decimal


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Profit", "last_name": "Owner"}, headers=headers)
    return resp.json()["id"]


def _create_property(client, headers, owner_id):
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Profit Center Test Unit", "owner_id": owner_id}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _create_tenant(client, headers):
    resp = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Profit", "last_name": "Tenant"}, headers=headers)
    return resp.json()["id"]


def _create_financial_account(client, headers, name="Profit Center Cash"):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "cash", "name": name, "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_rental_contract(client, headers, tenant_id, property_id, rent="1000.00"):
    resp = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ==================== Automatic property_id resolution ====================
def test_transaction_property_id_auto_filled_from_rental_contract(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract_id = _create_rental_contract(client, headers, tenant_id, prop["id"])
    account_id = _create_financial_account(client, headers)

    txn = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "tenant_payment", "amount": "1000.00", "account_id": account_id,
        "rental_contract_id": contract_id, "transaction_date": str(date.today()),
    }, headers=headers)
    assert txn.status_code == 201
    assert txn.json()["property_id"] == prop["id"]
    assert txn.json()["property_title"] == prop["title"]


def test_transaction_explicit_property_id_not_overridden(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop_a = _create_property(client, headers, owner_id)
    prop_b = _create_property(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract_id = _create_rental_contract(client, headers, tenant_id, prop_a["id"])
    account_id = _create_financial_account(client, headers)

    txn = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "tenant_payment", "amount": "1000.00", "account_id": account_id,
        "rental_contract_id": contract_id, "property_id": prop_b["id"], "transaction_date": str(date.today()),
    }, headers=headers)
    assert txn.status_code == 201
    assert txn.json()["property_id"] == prop_b["id"]  # explicit value wins over auto-fill


def test_invoice_property_id_auto_filled_from_rental_contract(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    tenant_id = _create_tenant(client, headers)
    contract_id = _create_rental_contract(client, headers, tenant_id, prop["id"])

    inv = client.post("/api/v1/financial/invoices", json={
        "tenant_id": tenant_id, "rental_contract_id": contract_id,
        "amount": "1000.00", "issue_date": str(date.today()), "due_date": str(date.today() + timedelta(days=15)),
    }, headers=headers)
    assert inv.status_code == 201
    assert inv.json()["property_id"] == prop["id"]
    assert inv.json()["property_title"] == prop["title"]


def test_auto_posted_journal_entry_lines_carry_property_id(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)

    coa_revenue = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "4900", "account_name": "PC Test Revenue", "account_type": "revenue"}, headers=headers).json()
    fin_account = client.post("/api/v1/financial/accounts", json={"account_type": "bank", "name": "PC Test Bank", "bank_name": "Test", "opening_balance": "0"}, headers=headers).json()
    client.put(f"/api/v1/financial/accounts/{fin_account['id']}", json={"gl_account_id": coa_revenue["id"]}, headers=headers)
    client.post("/api/v1/accounting/posting-rules", json={"transaction_type": "income", "offset_account_id": coa_revenue["id"]}, headers=headers)

    txn = client.post("/api/v1/financial/transactions", json={
        "transaction_type": "income", "amount": "500.00", "account_id": fin_account["id"],
        "property_id": prop["id"], "transaction_date": str(date.today()),
    }, headers=headers).json()

    entries = client.get("/api/v1/accounting/journal-entries", params={"source_type": "system"}, headers=headers).json()
    matching = [e for e in entries["items"] if e["source_transaction_id"] == txn["id"]]
    assert len(matching) == 1
    detail = client.get(f"/api/v1/accounting/journal-entries/{matching[0]['id']}", headers=headers).json()
    assert all(line["property_id"] == prop["id"] for line in detail["lines"])


# ==================== Property Profit & Loss ====================
def test_property_profit_and_loss(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    account_id = _create_financial_account(client, headers)

    client.post("/api/v1/financial/transactions", json={"transaction_type": "income", "amount": "800.00", "account_id": account_id, "property_id": prop["id"], "transaction_date": str(date.today())}, headers=headers)
    client.post("/api/v1/financial/transactions", json={"transaction_type": "expense", "amount": "300.00", "account_id": account_id, "property_id": prop["id"], "transaction_date": str(date.today())}, headers=headers)

    resp = client.get(f"/api/v1/properties/{prop['id']}/reports/profit-loss", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["property_id"] == prop["id"]
    assert Decimal(body["total_income"]) == Decimal("800.00")
    assert Decimal(body["total_expense"]) == Decimal("300.00")
    assert Decimal(body["net_profit"]) == Decimal("500.00")


def test_property_profit_and_loss_404_for_missing_property(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/properties/999999/reports/profit-loss", headers=headers)
    assert resp.status_code == 404


# ==================== Property Expense Report (reused method) ====================
def test_property_expense_report_reuses_portfolio_method(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    account_id = _create_financial_account(client, headers)
    client.post("/api/v1/financial/transactions", json={"transaction_type": "expense", "amount": "220.00", "account_id": account_id, "property_id": prop["id"], "category": "utilities", "transaction_date": str(date.today())}, headers=headers)

    resp = client.get(f"/api/v1/properties/{prop['id']}/reports/expense", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_expense"]) == Decimal("220.00")
    assert any(c["label"] == "utilities" for c in body["by_category"])


# ==================== Property Financial Dashboard ====================
def test_property_financial_dashboard(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    account_id = _create_financial_account(client, headers)
    client.post("/api/v1/financial/transactions", json={"transaction_type": "income", "amount": "1200.00", "account_id": account_id, "property_id": prop["id"], "transaction_date": str(date.today())}, headers=headers)

    resp = client.get(f"/api/v1/properties/{prop['id']}/financial-dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["property_id"] == prop["id"]
    assert Decimal(body["kpis"]["total_income_this_month"]) >= Decimal("1200.00")
    assert Decimal(body["kpis"]["net_profit_this_month"]) == Decimal(body["kpis"]["total_income_this_month"]) - Decimal(body["kpis"]["total_expense_this_month"])


# ==================== Property Cash Flow ====================
def test_property_cash_flow(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    account_id = _create_financial_account(client, headers)
    client.post("/api/v1/financial/transactions", json={"transaction_type": "income", "amount": "600.00", "account_id": account_id, "property_id": prop["id"], "transaction_date": str(date.today())}, headers=headers)
    client.post("/api/v1/financial/transactions", json={"transaction_type": "expense", "amount": "100.00", "account_id": account_id, "property_id": prop["id"], "transaction_date": str(date.today())}, headers=headers)

    resp = client.get(f"/api/v1/properties/{prop['id']}/reports/cash-flow", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["property_id"] == prop["id"]
    assert "net_cash_flow" in body
    assert Decimal(body["net_cash_flow"]) == Decimal("500.00")


# ==================== Property Income Statement (GL-grade, reused method) ====================
def test_property_income_statement_returns_expected_structure(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)
    resp = client.get(f"/api/v1/properties/{prop['id']}/reports/income-statement", params={"date_from": str(date.today() - timedelta(days=30)), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_revenue" in body and "total_expenses" in body and "net_income" in body


# ==================== Property Ledger & Balance Summary ====================
def test_property_ledger_and_balance_summary(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    prop = _create_property(client, headers, owner_id)

    cash = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "1150", "account_name": "PC Ledger Cash", "account_type": "asset"}, headers=headers).json()
    revenue = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "4950", "account_name": "PC Ledger Revenue", "account_type": "revenue"}, headers=headers).json()
    entry = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": cash["id"], "property_id": prop["id"], "debit_amount": "300.00"},
            {"account_id": revenue["id"], "property_id": prop["id"], "credit_amount": "300.00"},
        ],
    }, headers=headers).json()
    client.post(f"/api/v1/accounting/journal-entries/{entry['id']}/post", headers=headers)

    ledger = client.get(f"/api/v1/properties/{prop['id']}/reports/ledger", headers=headers)
    assert ledger.status_code == 200
    ledger_body = ledger.json()
    assert len(ledger_body["lines"]) == 2
    assert Decimal(ledger_body["total_debit"]) == Decimal("300.00")
    assert Decimal(ledger_body["total_credit"]) == Decimal("300.00")

    summary = client.get(f"/api/v1/properties/{prop['id']}/reports/balance-summary", params={"as_of_date": str(date.today())}, headers=headers)
    assert summary.status_code == 200
    summary_body = summary.json()
    assert any(l["account_code"] == "1150" for l in summary_body["lines"])
    assert any(l["account_code"] == "4950" for l in summary_body["lines"])


def test_property_journal_entry_line_rejects_invalid_property_id(client, seeded_admin):
    headers = _auth_headers(client)
    cash = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "1160", "account_name": "PC Invalid Test", "account_type": "asset"}, headers=headers).json()
    revenue = client.post("/api/v1/accounting/chart-of-accounts", json={"account_code": "4960", "account_name": "PC Invalid Test Rev", "account_type": "revenue"}, headers=headers).json()
    resp = client.post("/api/v1/accounting/journal-entries", json={
        "entry_date": str(date.today()),
        "lines": [
            {"account_id": cash["id"], "property_id": 999999, "debit_amount": "100.00"},
            {"account_id": revenue["id"], "credit_amount": "100.00"},
        ],
    }, headers=headers)
    assert resp.status_code == 400


# ==================== Regression: portfolio-wide reports unaffected ====================
def test_portfolio_income_statement_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/accounting/reports/income-statement", params={"date_from": str(date.today() - timedelta(days=30)), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    assert "net_income" in resp.json()


def test_portfolio_cash_flow_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/accounting/reports/cash-flow", params={"date_from": str(date.today() - timedelta(days=30)), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    assert "opening_cash_balance" in resp.json()


def test_portfolio_expense_report_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/expenses", headers=headers)
    assert resp.status_code == 200
    assert "by_property" in resp.json()


def test_portfolio_dashboard_analytics_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    assert "kpis" in resp.json()


def test_portfolio_profit_report_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/profit", headers=headers)
    assert resp.status_code == 200
    assert "by_property" in resp.json()


def test_property_profit_center_endpoints_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/properties/1/financial-dashboard")
    assert resp.status_code == 401
