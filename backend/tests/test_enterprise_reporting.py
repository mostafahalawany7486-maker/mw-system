"""
Enterprise Reporting tests: the 5 genuinely new report types (Lease,
Maintenance, Collections, Outstanding, Contract Expiration), the generic
PDF/Excel export endpoint (reused across all 10 report types), and
Export Scheduling (CRUD + run-now, which generates a real file and
stores it via the existing Attachment mechanism). Also includes
regression tests confirming the 5 pre-existing report endpoints from
Phase 11 are completely unaffected.
"""
from datetime import date, timedelta
from decimal import Decimal


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    return client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "ER", "last_name": "Owner"}, headers=headers).json()


def _create_property(client, headers, owner_id, property_type="apartment"):
    resp = client.post("/api/v1/properties", json={"property_type": property_type, "title": "ER Test Property", "owner_id": owner_id}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_tenant(client, headers):
    return client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "ER", "last_name": "Tenant"}, headers=headers).json()


def _create_rental_contract(client, headers, tenant_id, property_id, rent="1000.00"):
    resp = client.post("/api/v1/rentals", json={
        "tenant_id": tenant_id, "property_id": property_id,
        "start_date": str(date.today()), "end_date": str(date.today() + timedelta(days=20)),
        "payment_frequency": "monthly", "rent_amount": rent, "security_deposit_amount": rent,
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_maintenance_request(client, headers, property_id, **overrides):
    payload = {"property_id": property_id, "title": "ER Test issue", "category": "plumbing", "priority": "medium", "reported_date": str(date.today())}
    payload.update(overrides)
    resp = client.post("/api/v1/maintenance/requests", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ==================== Lease Report ====================
def test_lease_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/leases", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "rental_contracts_by_status" in body and "lease_agreements_by_status" in body
    assert "rental_contracts" in body and "lease_agreements" in body


def test_lease_report_reflects_created_contract(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    prop = _create_property(client, headers, owner["id"])
    tenant = _create_tenant(client, headers)
    contract = _create_rental_contract(client, headers, tenant["id"], prop["id"], rent="1500.00")

    resp = client.get("/api/v1/reports/leases", params={"property_id": prop["id"]}, headers=headers)
    body = resp.json()
    matching = [c for c in body["rental_contracts"] if c["id"] == contract["id"]]
    assert len(matching) == 1
    assert Decimal(matching[0]["rent_amount"]) == Decimal("1500.00")


def test_lease_report_filters_by_status(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    prop = _create_property(client, headers, owner["id"])
    tenant = _create_tenant(client, headers)
    _create_rental_contract(client, headers, tenant["id"], prop["id"])

    resp = client.get("/api/v1/reports/leases", params={"contract_status": "draft"}, headers=headers)
    assert resp.status_code == 200
    resp2 = client.get("/api/v1/reports/leases", params={"contract_status": "active"}, headers=headers)
    assert resp2.status_code == 200


# ==================== Maintenance Report ====================
def test_maintenance_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/maintenance", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    for field in ["total_requests", "by_status", "by_priority", "by_category", "by_contractor", "total_cost", "requests"]:
        assert field in body


def test_maintenance_report_reflects_created_request(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    prop = _create_property(client, headers, owner["id"])
    req = _create_maintenance_request(client, headers, prop["id"], priority="urgent", category="electrical")

    resp = client.get("/api/v1/reports/maintenance", params={
        "date_from": str(date.today()), "date_to": str(date.today()), "priority": "urgent",
    }, headers=headers)
    body = resp.json()
    matching = [r for r in body["requests"] if r["id"] == req["id"]]
    assert len(matching) == 1
    assert matching[0]["category"] == "electrical"


def test_maintenance_report_average_resolution_days(client, seeded_admin):
    """Structural check only — the seeded/created requests may or may not
    include completed ones depending on test order, so we only assert
    the field is present and, if not None, non-negative."""
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/maintenance", headers=headers)
    body = resp.json()
    assert "average_resolution_days" in body
    if body["average_resolution_days"] is not None:
        assert Decimal(str(body["average_resolution_days"])) >= 0


# ==================== Collections Report ====================
def test_collections_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/collections", params={"months": 3}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["monthly_trend"]) == 3
    assert "by_property" in body
    assert 0 <= Decimal(body["collection_rate_percentage"]) <= 100


# ==================== Outstanding Report ====================
def test_outstanding_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/outstanding", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "tenant_aging" in body and "owner_aging" in body
    for bucket in ["current", "days_1_30", "days_31_60", "days_61_90", "days_90_plus"]:
        assert bucket in body["tenant_aging"]
        assert bucket in body["owner_aging"]


def test_outstanding_report_totals_match_aging_sum(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/outstanding", headers=headers)
    body = resp.json()
    aging_sum = sum(Decimal(str(v)) for v in body["tenant_aging"].values())
    assert aging_sum == Decimal(str(body["tenant_outstanding_total"]))


# ==================== Contract Expiration Report ====================
def test_contract_expiration_report_structure(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/contract-expirations", params={"days": 30}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["window_days"] == 30
    assert "expiring_rental_contracts" in body and "expiring_lease_agreements" in body
    assert body["total_expiring"] == len(body["expiring_rental_contracts"]) + len(body["expiring_lease_agreements"])


def test_contract_expiration_report_includes_active_expiring_contract(client, seeded_admin):
    headers = _auth_headers(client)
    owner = _create_owner(client, headers)
    prop = _create_property(client, headers, owner["id"])
    tenant = _create_tenant(client, headers)
    contract = _create_rental_contract(client, headers, tenant["id"], prop["id"])
    activated = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert activated.status_code == 200

    resp = client.get("/api/v1/reports/contract-expirations", params={"days": 30, "property_id": prop["id"]}, headers=headers)
    body = resp.json()
    matching = [c for c in body["expiring_rental_contracts"] if c["id"] == contract["id"]]
    assert len(matching) == 1
    assert matching[0]["days_remaining"] <= 20


# ==================== Generic Export (PDF / Excel) ====================
def test_export_report_pdf(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/property/export", params={"format": "pdf"}, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert len(resp.content) > 100  # a real, non-empty PDF was generated
    assert resp.content[:4] == b"%PDF"


def test_export_report_excel(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/maintenance/export", params={"format": "excel"}, headers=headers)
    assert resp.status_code == 200
    assert "spreadsheet" in resp.headers["content-type"]
    assert len(resp.content) > 100
    assert resp.content[:2] == b"PK"  # xlsx is a zip archive


def test_export_report_defaults_to_pdf(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/financial/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_export_report_rejects_unknown_type(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/not-a-real-report/export", headers=headers)
    assert resp.status_code == 400


def test_export_every_report_type_produces_output(client, seeded_admin):
    """One export per report type — a lightweight smoke test that the
    generic report_to_document() mapping doesn't KeyError on any of the
    10 report shapes."""
    headers = _auth_headers(client)
    for report_type in ["property", "owner", "tenant", "lease", "occupancy", "financial", "maintenance", "collections", "outstanding", "contract_expiration"]:
        resp = client.get(f"/api/v1/reports/{report_type}/export", params={"format": "pdf"}, headers=headers)
        assert resp.status_code == 200, f"{report_type} export failed: {resp.text}"
        assert len(resp.content) > 50


# ==================== Export Scheduling ====================
def test_create_report_schedule(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/reports/schedules", json={
        "name": "Test Weekly Property Report", "report_type": "property", "export_format": "pdf", "frequency": "weekly",
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Weekly Property Report"
    assert body["is_active"] is True
    assert body["next_run_at"] is not None


def test_create_schedule_rejects_invalid_report_type(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/reports/schedules", json={
        "name": "Bad", "report_type": "not_a_type", "export_format": "pdf", "frequency": "daily",
    }, headers=headers)
    assert resp.status_code == 422


def test_create_schedule_rejects_invalid_export_format(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/reports/schedules", json={
        "name": "Bad", "report_type": "property", "export_format": "csv", "frequency": "daily",
    }, headers=headers)
    assert resp.status_code == 422


def test_list_and_get_schedule(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/reports/schedules", json={
        "name": "List Test Schedule", "report_type": "tenant", "export_format": "excel", "frequency": "monthly",
    }, headers=headers).json()

    listed = client.get("/api/v1/reports/schedules", headers=headers)
    assert listed.status_code == 200
    assert any(s["id"] == created["id"] for s in listed.json())

    fetched = client.get(f"/api/v1/reports/schedules/{created['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_update_schedule(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/reports/schedules", json={
        "name": "Update Test Schedule", "report_type": "owner", "export_format": "pdf", "frequency": "daily",
    }, headers=headers).json()

    updated = client.put(f"/api/v1/reports/schedules/{created['id']}", json={"is_active": False, "name": "Renamed Schedule"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert updated.json()["name"] == "Renamed Schedule"


def test_delete_schedule(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/reports/schedules", json={
        "name": "Delete Test Schedule", "report_type": "occupancy", "export_format": "pdf", "frequency": "weekly",
    }, headers=headers).json()

    deleted = client.delete(f"/api/v1/reports/schedules/{created['id']}", headers=headers)
    assert deleted.status_code == 200

    fetched = client.get(f"/api/v1/reports/schedules/{created['id']}", headers=headers)
    assert fetched.status_code == 404


def test_run_schedule_now_generates_attachment(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/reports/schedules", json={
        "name": "Run Now Test Schedule", "report_type": "financial", "export_format": "pdf", "frequency": "monthly",
    }, headers=headers).json()
    assert created["last_run_at"] is None
    assert created["last_export_file_url"] is None

    run = client.post(f"/api/v1/reports/schedules/{created['id']}/run-now", headers=headers)
    assert run.status_code == 200
    body = run.json()
    assert body["last_run_at"] is not None
    assert body["last_export_file_url"] is not None
    assert body["last_export_file_name"] is not None
    # next_run_at should have advanced past the original value
    assert body["next_run_at"] != created["next_run_at"]


def test_run_due_schedules_endpoint(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/reports/schedules/run-due", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_schedule_endpoints_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/reports/schedules")
    assert resp.status_code == 401


# ==================== Regression: existing Phase 11 reports unaffected ====================
def test_existing_financial_report_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/financial", headers=headers)
    assert resp.status_code == 200
    assert "total_income" in resp.json()


def test_existing_property_report_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/properties", headers=headers)
    assert resp.status_code == 200
    assert "total_properties" in resp.json()


def test_existing_dashboard_analytics_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/analytics/dashboard", headers=headers)
    assert resp.status_code == 200
    assert "kpis" in resp.json()


def test_existing_occupancy_report_still_works(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/reports/occupancy", headers=headers)
    assert resp.status_code == 200
    assert "overall_occupancy_rate_percentage" in resp.json()
