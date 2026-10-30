"""
Lease Agreement tests: creation validation, status transitions (draft ->
active -> terminated/renewed), payment schedule generation, and permission
enforcement.
"""
from datetime import date, timedelta


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_owner(client, headers):
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Lease", "last_name": "Owner"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _lease_payload(owner_id, **overrides):
    payload = {
        "owner_id": owner_id,
        "property_reference": "Test Unit 1A",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=365)),
        "payment_frequency": "monthly",
        "rent_amount": "1000.00",
        "security_deposit_amount": "2000.00",
    }
    payload.update(overrides)
    return payload


def test_create_lease_success(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["contract_status"] == "draft"
    assert body["contract_number"].startswith("LSE-")


def test_create_lease_end_before_start_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    payload = _lease_payload(owner_id, start_date=str(date.today()), end_date=str(date.today() - timedelta(days=10)))
    resp = client.post("/api/v1/leases", json=payload, headers=headers)
    assert resp.status_code == 422


def test_create_lease_invalid_owner_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/leases", json=_lease_payload(999999), headers=headers)
    assert resp.status_code == 400


def test_create_lease_negative_rent_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/leases", json=_lease_payload(owner_id, rent_amount="-100"), headers=headers)
    assert resp.status_code == 422


def test_invalid_payment_frequency_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    resp = client.post("/api/v1/leases", json=_lease_payload(owner_id, payment_frequency="weekly"), headers=headers)
    assert resp.status_code == 422


def test_activate_lease_flow(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    resp = client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contract_status"] == "active"


def test_cannot_activate_already_active_lease(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    resp = client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    assert resp.status_code == 409


def test_terminate_requires_active_status(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    # still draft — terminate should fail
    resp = client.post(f"/api/v1/leases/{lease['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "test",
    }, headers=headers)
    assert resp.status_code == 409


def test_terminate_active_lease(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    resp = client.post(f"/api/v1/leases/{lease['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "Owner sold property",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contract_status"] == "terminated"


def test_renew_lease_creates_new_contract(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)

    new_end = str(date.today() + timedelta(days=730))
    resp = client.post(f"/api/v1/leases/{lease['id']}/renew", json={"new_end_date": new_end}, headers=headers)
    assert resp.status_code == 200
    renewed = resp.json()
    assert renewed["contract_number"] != lease["contract_number"]
    assert renewed["renewed_from_lease_id"] == lease["id"]

    old = client.get(f"/api/v1/leases/{lease['id']}", headers=headers).json()
    assert old["contract_status"] == "renewed"


def test_cannot_renew_draft_lease(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    resp = client.post(f"/api/v1/leases/{lease['id']}/renew", json={"new_end_date": str(date.today() + timedelta(days=400))}, headers=headers)
    assert resp.status_code == 409


def test_generate_monthly_payment_schedule(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(
        owner_id, start_date=str(date(2026, 1, 1)), end_date=str(date(2026, 6, 1)), payment_frequency="monthly",
    ), headers=headers).json()
    resp = client.post(f"/api/v1/leases/{lease['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert resp.status_code == 200
    installments = resp.json()
    assert len(installments) == 6  # Jan through Jun inclusive
    assert all(i["payment_status"] == "pending" for i in installments)


def test_generate_schedule_twice_without_overwrite_fails(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    resp = client.post(f"/api/v1/leases/{lease['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers)
    assert resp.status_code == 409


def test_mark_installment_paid(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    installments = client.post(f"/api/v1/leases/{lease['id']}/installments/generate", json={"overwrite_existing": False}, headers=headers).json()
    first = installments[0]
    resp = client.put(f"/api/v1/leases/{lease['id']}/installments/{first['id']}", json={
        "payment_status": "paid", "paid_date": str(date.today()), "payment_method": "bank_transfer",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "paid"


def test_lease_dashboard_summary(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers)
    resp = client.get("/api/v1/leases/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_leases"] >= 1


def test_maintenance_sweep_runs(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/leases/maintenance/run", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "leases_auto_expired" in body
    assert "renewal_reminders_sent" in body


def test_leases_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/leases")
    assert resp.status_code == 401


def test_cannot_edit_terminated_lease(client, seeded_admin):
    headers = _auth_headers(client)
    owner_id = _create_owner(client, headers)
    lease = client.post("/api/v1/leases", json=_lease_payload(owner_id), headers=headers).json()
    client.post(f"/api/v1/leases/{lease['id']}/activate", headers=headers)
    client.post(f"/api/v1/leases/{lease['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "test",
    }, headers=headers)
    resp = client.put(f"/api/v1/leases/{lease['id']}", json={"rent_amount": "9999.00"}, headers=headers)
    assert resp.status_code == 409
