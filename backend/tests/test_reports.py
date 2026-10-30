"""
Reports tests: Financial, Tenant, Owner, Property, Vacancy, Occupancy,
Income, Expense, Profit reports, and Dashboard Analytics — all computed
live from Phase 1-10 data, so tests build the minimum fixtures needed
through the real APIs (not direct DB inserts) to exercise the actual
aggregation logic end-to-end.
"""
from datetime import date
from decimal import Decimal


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    return client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Report", "last_name": "Owner"}, headers=headers).json()


def _create_property(client, headers, owner_id, property_type="apartment"):
    resp = client.post("/api/v1/properties", json={"property_type": property_type, "title": "Report Test Property", "owner_id": owner_id}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_tenant(client, headers):
    return client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Report", "last_name": "Tenant"}, headers=headers).json()


def _create_financial_account(client, headers):
    resp = client.post("/api/v1/financial/accounts", json={"account_type": "cash", "name": "Report Test Cash", "opening_balance": "0"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _record_transaction(client, headers, **kwargs):
    payload = {"transaction_date": str(date.today())}
    payload.update(kwargs)
    resp = client.post("/api/v1/financial/transactions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------- Financial Reports ----------------
def test_financial_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/financial", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "total_income" in body and "total_expense" in body and "net_cash_flow" in body
    assert Decimal(body["net_cash_flow"]) == Decimal(body["total_income"]) - Decimal(body["total_expense"])


def test_financial_report_reflects_recorded_transactions(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="income", amount="400.00", account_id=account["id"])
    _record_transaction(client, headers, transaction_type="expense", amount="150.00", account_id=account["id"])

    resp = client.get("/api/v1/reports/financial", params={
        "date_from": str(date.today()), "date_to": str(date.today()),
    }, headers=headers)
    body = resp.json()
    assert Decimal(body["total_income"]) >= Decimal("400.00")
    assert Decimal(body["total_expense"]) >= Decimal("150.00")


# ---------------- Tenant Reports ----------------
def test_tenant_report_counts(client, seeded_admin):
    headers = _auth_headers(client)
    _create_tenant(client, headers)
    resp = client.get("/api/v1/reports/tenants", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tenants"] >= 1
    assert body["individual_tenants"] + body["company_tenants"] == body["total_tenants"]


def test_tenant_report_top_payers(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = _create_tenant(client, headers)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="tenant_payment", amount="1000.00", account_id=account["id"], tenant_id=tenant["id"])

    resp = client.get("/api/v1/reports/tenants", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    body = resp.json()
    matching = [t for t in body["top_tenants_by_payment"] if t["tenant_id"] == tenant["id"]]
    assert len(matching) == 1
    assert Decimal(matching[0]["total_paid"]) == Decimal("1000.00")


# ---------------- Owner Reports ----------------
def test_owner_report_counts(client, seeded_admin):
    headers = _auth_headers(client)
    _create_owner(client, headers)
    resp = client.get("/api/v1/reports/owners", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_owners"] >= 1


def test_owner_report_top_by_properties(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    _create_property(client, headers, owner["id"])
    _create_property(client, headers, owner["id"])

    resp = client.get("/api/v1/reports/owners", headers=headers)
    body = resp.json()
    matching = [o for o in body["top_owners_by_properties"] if o["owner_id"] == owner["id"]]
    assert len(matching) == 1
    assert matching[0]["property_count"] >= 2


# ---------------- Property Reports ----------------
def test_property_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    _create_property(client, headers, owner["id"], property_type="villa")
    resp = client.get("/api/v1/reports/properties", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_properties"] >= 1
    types = {t["property_type"] for t in body["by_type"]}
    assert "villa" in types


# ---------------- Vacancy Reports ----------------
def test_vacancy_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    _create_property(client, headers, owner["id"])
    resp = client.get("/api/v1/reports/vacancy", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_properties"] == body["vacant_count"] + body["leased_count"] + body["other_count"]
    assert 0 <= Decimal(body["vacancy_rate_percentage"]) <= 100


def test_vacancy_report_excludes_buildings(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    building = _create_property(client, headers, owner["id"], property_type="building")
    resp = client.get("/api/v1/reports/vacancy", headers=headers)
    body = resp.json()
    ids_in_vacant_list = [p["property_id"] for p in body["vacant_properties"]]
    assert building["id"] not in ids_in_vacant_list


# ---------------- Occupancy Reports ----------------
def test_occupancy_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/occupancy", params={"months": 3}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["trend"]) == 3
    assert 0 <= Decimal(body["overall_occupancy_rate_percentage"]) <= 100


# ---------------- Unit Reports (Phase 2.0) ----------------
def test_units_report_portfolio_wide(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    resp = client.get("/api/v1/reports/units", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scoped_to_property_id"] is None
    assert "by_status" in body and "by_type" in body and "units" in body


def test_units_report_scoped_to_building(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    building = client.post("/api/v1/properties", json={"property_type": "building", "title": "Report Tower", "owner_id": owner["id"]}, headers=headers).json()
    client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Report Unit 1", "owner_id": owner["id"], "parent_property_id": building["id"]}, headers=headers)
    client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Report Unit 2", "owner_id": owner["id"], "parent_property_id": building["id"]}, headers=headers)

    resp = client.get("/api/v1/reports/units", params={"property_id": building["id"]}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scoped_to_property_id"] == building["id"]
    assert body["scoped_to_property_title"] == "Report Tower"
    assert body["total_units"] == 2
    assert len(body["units"]) == 2
    assert all(u["building_title"] == "Report Tower" for u in body["units"])


# ---------------- Income Reports ----------------
def test_income_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="income", amount="250.00", account_id=account["id"], category="parking_fee")

    resp = client.get("/api/v1/reports/income", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_income"]) >= Decimal("250.00")
    categories = {c["label"] for c in body["by_category"]}
    assert "parking_fee" in categories


def test_income_report_trend_has_six_months_by_default(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/income", headers=headers)
    body = resp.json()
    assert len(body["trend"]) == 6


# ---------------- Expense Reports ----------------
def test_expense_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="expense", amount="80.00", account_id=account["id"], category="utilities")

    resp = client.get("/api/v1/reports/expenses", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["total_expense"]) >= Decimal("80.00")
    assert "total_maintenance_cost" in body


# ---------------- Profit Reports ----------------
def test_profit_report_computation(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="income", amount="600.00", account_id=account["id"])
    _record_transaction(client, headers, transaction_type="expense", amount="200.00", account_id=account["id"])

    resp = client.get("/api/v1/reports/profit", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert Decimal(body["net_profit"]) == Decimal(body["total_income"]) - Decimal(body["total_expense"])


def test_profit_report_by_property(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    prop = _create_property(client, headers, owner["id"])
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="income", amount="900.00", account_id=account["id"], property_id=prop["id"])

    resp = client.get("/api/v1/reports/profit", params={"date_from": str(date.today()), "date_to": str(date.today())}, headers=headers)
    body = resp.json()
    matching = [p for p in body["by_property"] if p["property_id"] == prop["id"]]
    assert len(matching) == 1
    assert Decimal(matching[0]["income"]) == Decimal("900.00")


# ---------------- Dashboard Analytics ----------------
def test_dashboard_analytics_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "kpis" in body and "monthly_trend" in body and "top_properties_by_revenue" in body
    assert len(body["monthly_trend"]) >= 1
    kpis = body["kpis"]
    assert Decimal(kpis["net_profit_this_month"]) == Decimal(kpis["total_income_this_month"]) - Decimal(kpis["total_expense_this_month"])


def test_dashboard_analytics_kpis_reflect_data(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    _create_property(client, headers, owner["id"])
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    body = resp.json()
    assert body["kpis"]["total_properties"] >= 1


# ---------------- Enterprise Dashboard extension ----------------
def test_dashboard_analytics_extended_fields_present(client, seeded_admin):
    """New fields must be additive — nothing from the original response
    shape may be removed or renamed (backward compatibility)."""
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    kpis = body["kpis"]
    for field in ["total_units", "occupied_units", "vacant_units", "occupancy_rate_percentage", "contracts_expiring_soon"]:
        assert field in kpis
    for field in ["properties_by_type", "properties_by_availability", "occupancy_by_type", "cash_flow_by_type"]:
        assert field in body
    # original fields must still be present, unchanged
    for field in ["total_properties", "occupied_properties", "vacancy_rate_percentage", "total_outstanding_tenant", "total_outstanding_owner"]:
        assert field in kpis


def test_dashboard_occupancy_and_vacancy_rates_are_complementary(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    prop = _create_property(client, headers, owner["id"])
    assert prop["id"]  # ensure at least one leasable property exists
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    kpis = resp.json()["kpis"]
    assert Decimal(kpis["occupancy_rate_percentage"]) + Decimal(kpis["vacancy_rate_percentage"]) == Decimal("100.00")


def test_dashboard_units_breakdown_consistent(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    kpis = resp.json()["kpis"]
    assert kpis["occupied_units"] + kpis["vacant_units"] <= kpis["total_units"]
    assert kpis["occupied_units"] <= kpis["total_units"]
    assert kpis["vacant_units"] <= kpis["total_units"]
    assert kpis["occupied_units"] == kpis["occupied_properties"]  # same underlying figure, new name


def test_dashboard_analytics_accepts_custom_date_range(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="income", amount="777.00", account_id=account["id"])

    resp = client.get("/api/v1/reports/analytics/dashboard", params={
        "date_from": str(date.today()), "date_to": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 200
    assert Decimal(resp.json()["kpis"]["total_income_this_month"]) >= Decimal("777.00")


def test_dashboard_analytics_backward_compatible_with_no_params(client, seeded_admin):
    """The original zero-argument call must behave identically to before
    this extension — same 'this month to date' default window."""
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["kpis"]["total_income_this_month"] is not None
    assert len(body["monthly_trend"]) == 6


def test_dashboard_cash_flow_by_type_structure(client, seeded_admin):
    headers = _auth_headers(client)
    account = _create_financial_account(client, headers)
    _record_transaction(client, headers, transaction_type="expense", amount="50.00", account_id=account["id"])
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    cash_flow = resp.json()["cash_flow_by_type"]
    assert any(c["label"] == "expense" for c in cash_flow)


# ---------------- Permissions ----------------
def test_reports_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/reports/financial")
    assert resp.status_code == 401
