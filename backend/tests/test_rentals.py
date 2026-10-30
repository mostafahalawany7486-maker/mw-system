"""
Rental Contract tests: creation validation, status transitions, renewal,
payment schedule generation with discounts/taxes, late fee assessment,
and permission enforcement.
"""
from datetime import date, timedelta


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_tenant(client, headers):
    resp = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Rental", "last_name": "Tenant"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_property(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Prop", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Rental Test Unit", "owner_id": owner["id"]}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _contract_payload(tenant_id, property_id, **overrides):
    payload = {
        "tenant_id": tenant_id,
        "property_id": property_id,
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly",
        "rent_amount": "1000.00",
        "security_deposit_amount": "2000.00",
    }
    payload.update(overrides)
    return payload


def test_create_contract_success(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["contract_status"] == "draft"
    assert body["contract_number"].startswith("RNT-")


def test_create_contract_end_before_start_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    payload = _contract_payload(tenant_id, property_id, start_date=str(date.today()), end_date=str(date.today() - timedelta(days=10)))
    resp = client.post("/api/v1/rentals", json=payload, headers=headers)
    assert resp.status_code == 422


def test_create_contract_invalid_tenant_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/rentals", json=_contract_payload(999999, property_id), headers=headers)
    assert resp.status_code == 400


def test_create_contract_invalid_property_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    resp = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, 999999), headers=headers)
    assert resp.status_code == 400


def test_create_contract_for_blacklisted_tenant_allowed_with_warning(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Bad", "last_name": "Tenant"}, headers=headers).json()
    client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": "test"}, headers=headers)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/rentals", json=_contract_payload(tenant["id"], property_id), headers=headers)
    assert resp.status_code == 201  # allowed, not blocked
    assert resp.json()["tenant_is_blacklisted"] is True


def test_percentage_discount_out_of_range_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    payload = _contract_payload(tenant_id, property_id, discount_type="percentage", discount_value="150")
    resp = client.post("/api/v1/rentals", json=payload, headers=headers)
    assert resp.status_code == 422


def test_invalid_tax_rate_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    payload = _contract_payload(tenant_id, property_id, tax_rate="150")
    resp = client.post("/api/v1/rentals", json=payload, headers=headers)
    assert resp.status_code == 422


def test_activate_contract_sets_property_leased(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    contract = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers).json()
    resp = client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contract_status"] == "active"
    prop = client.get(f"/api/v1/properties/{property_id}", headers=headers).json()
    assert prop["availability_status"] == "leased"


def test_terminate_contract_frees_property(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    contract = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers).json()
    client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    resp = client.post(f"/api/v1/rentals/{contract['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "Tenant moved out",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contract_status"] == "terminated"
    prop = client.get(f"/api/v1/properties/{property_id}", headers=headers).json()
    assert prop["availability_status"] == "available"


def test_renew_contract_creates_new_row(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    contract = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers).json()
    client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)

    new_end = str(date.today() + timedelta(days=730))
    resp = client.post(f"/api/v1/rentals/{contract['id']}/renew", json={"new_end_date": new_end}, headers=headers)
    assert resp.status_code == 200
    renewed = resp.json()
    assert renewed["contract_number"] != contract["contract_number"]
    assert renewed["renewed_from_contract_id"] == contract["id"]

    old = client.get(f"/api/v1/rentals/{contract['id']}", headers=headers).json()
    assert old["contract_status"] == "renewed"


def test_generate_schedule_applies_discount_and_tax(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    payload = _contract_payload(
        tenant_id, property_id, rent_amount="1000.00",
        discount_type="fixed", discount_value="50.00", tax_rate="10.00",
    )
    contract = client.post("/api/v1/rentals", json=payload, headers=headers).json()
    resp = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert resp.status_code == 200
    installments = resp.json()
    first = installments[0]
    assert first["discount_amount"] == "50.00"
    # tax computed on (1000 - 50) * 10% = 95.00
    assert first["tax_amount"] == "95.00"
    assert float(first["total_payable"]) == 1000 - 50 + 95 + 0


def test_generate_schedule_twice_without_overwrite_fails(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    contract = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers).json()
    client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    resp = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert resp.status_code == 409


def test_mark_installment_paid(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    contract = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers).json()
    installments = client.post(f"/api/v1/rentals/{contract['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers).json()
    first = installments[0]
    resp = client.put(f"/api/v1/rentals/{contract['id']}/installments/{first['id']}", json={
        "payment_status": "paid", "paid_date": str(date.today()), "payment_method": "bank_transfer",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "paid"


def test_rental_dashboard_summary(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers)
    resp = client.get("/api/v1/rentals/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_contracts"] >= 1


def test_maintenance_sweep_runs(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/rentals/maintenance/run", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "contracts_auto_expired" in body
    assert "late_fees_assessed" in body


def test_rentals_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/rentals")
    assert resp.status_code == 401


def test_cannot_edit_terminated_contract(client, seeded_admin):
    headers = _auth_headers(client)
    tenant_id = _create_tenant(client, headers)
    property_id = _create_property(client, headers)
    contract = client.post("/api/v1/rentals", json=_contract_payload(tenant_id, property_id), headers=headers).json()
    client.post(f"/api/v1/rentals/{contract['id']}/activate", headers=headers)
    client.post(f"/api/v1/rentals/{contract['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "test",
    }, headers=headers)
    resp = client.put(f"/api/v1/rentals/{contract['id']}", json={"rent_amount": "9999.00"}, headers=headers)
    assert resp.status_code == 409
