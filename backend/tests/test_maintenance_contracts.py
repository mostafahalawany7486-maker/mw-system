"""
Maintenance Contract tests: creation validation, status transitions
(draft -> active -> terminated/renewed), service-visit logging, the
on-demand renewal sweep, and permission enforcement. Mirrors
test_leases.py's structure closely since MaintenanceContract deliberately
follows the same status-machine shape as LeaseAgreement.
"""
from datetime import date, timedelta


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_property(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Contract", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={"property_type": "building", "title": "Contract Test Tower", "owner_id": owner["id"]}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_contractor(client, headers, specialty="elevator"):
    resp = client.post("/api/v1/maintenance/contractors", json={"company_name": "Test Elevator Co", "specialty": specialty}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _contract_payload(property_id, contractor_id, **overrides):
    payload = {
        "property_id": property_id,
        "contractor_id": contractor_id,
        "service_type": "elevator",
        "title": "Annual Elevator Maintenance",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=365)),
        "visit_frequency": "quarterly",
        "annual_cost": "8000.00",
    }
    payload.update(overrides)
    return payload


def _create_contract(client, headers, property_id, contractor_id, **overrides):
    resp = client.post("/api/v1/maintenance/contracts", json=_contract_payload(property_id, contractor_id, **overrides), headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ---------------- Creation & validation ----------------
def test_create_contract_defaults_to_draft(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    assert contract["contract_status"] == "draft"
    assert contract["contract_number"].startswith("MTC-")
    # next_service_due_date auto-computed from visit_frequency when omitted
    assert contract["next_service_due_date"] is not None


def test_invalid_service_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    resp = client.post(
        "/api/v1/maintenance/contracts",
        json=_contract_payload(property_id, contractor_id, service_type="wizardry"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_invalid_property_id_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    contractor_id = _create_contractor(client, headers)
    resp = client.post(
        "/api/v1/maintenance/contracts",
        json=_contract_payload(999999, contractor_id),
        headers=headers,
    )
    assert resp.status_code == 400


def test_end_date_before_start_date_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    resp = client.post(
        "/api/v1/maintenance/contracts",
        json=_contract_payload(property_id, contractor_id, start_date=str(date.today()), end_date=str(date.today() - timedelta(days=1))),
        headers=headers,
    )
    assert resp.status_code == 400


# ---------------- Status transitions ----------------
def test_activate_contract_flow(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contract_status"] == "active"


def test_cannot_activate_already_active_contract(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)
    assert resp.status_code == 409


def test_terminate_requires_active_status(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "test",
    }, headers=headers)
    assert resp.status_code == 409


def test_terminate_active_contract(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "Building sold",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contract_status"] == "terminated"


def test_cannot_edit_terminated_contract(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/terminate", json={
        "terminated_date": str(date.today()), "termination_reason": "test",
    }, headers=headers)
    resp = client.put(f"/api/v1/maintenance/contracts/{contract['id']}", json={"annual_cost": "9999.00"}, headers=headers)
    assert resp.status_code == 409


# ---------------- Renewal ----------------
def test_renew_contract_creates_new_row(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)

    new_end = str(date.today() + timedelta(days=730))
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/renew", json={"new_end_date": new_end}, headers=headers)
    assert resp.status_code == 200
    renewed = resp.json()
    assert renewed["contract_number"] != contract["contract_number"]
    assert renewed["renewed_from_contract_id"] == contract["id"]
    assert renewed["contract_status"] == "active"

    old = client.get(f"/api/v1/maintenance/contracts/{contract['id']}", headers=headers).json()
    assert old["contract_status"] == "renewed"


def test_cannot_renew_draft_contract(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    resp = client.post(
        f"/api/v1/maintenance/contracts/{contract['id']}/renew",
        json={"new_end_date": str(date.today() + timedelta(days=400))},
        headers=headers,
    )
    assert resp.status_code == 409


# ---------------- Service visits ----------------
def test_log_service_visit_advances_next_due_date(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id, visit_frequency="quarterly")
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)

    before = client.get(f"/api/v1/maintenance/contracts/{contract['id']}", headers=headers).json()
    visit_date = str(date.today())
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/log-visit", json={"visit_date": visit_date, "notes": "Quarterly inspection done"}, headers=headers)
    assert resp.status_code == 200
    after = resp.json()
    assert after["next_service_due_date"] != before["next_service_due_date"]


def test_cannot_log_visit_on_draft_contract(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    resp = client.post(f"/api/v1/maintenance/contracts/{contract['id']}/log-visit", json={"visit_date": str(date.today())}, headers=headers)
    assert resp.status_code == 409


# ---------------- Sweep, dashboard, listing ----------------
def test_maintenance_contracts_sweep_runs(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/maintenance/contracts/maintenance/run", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "contracts_auto_expired" in body
    assert "renewal_reminders_sent" in body
    assert "service_due_notifications_sent" in body


def test_sweep_expires_overdue_active_contract(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(
        client, headers, property_id, contractor_id,
        start_date=str(date.today() - timedelta(days=400)), end_date=str(date.today() - timedelta(days=1)),
    )
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)

    resp = client.post("/api/v1/maintenance/contracts/maintenance/run", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["contracts_auto_expired"] >= 1

    refreshed = client.get(f"/api/v1/maintenance/contracts/{contract['id']}", headers=headers).json()
    assert refreshed["contract_status"] == "expired"


def test_contracts_dashboard_summary(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    _create_contract(client, headers, property_id, contractor_id)
    resp = client.get("/api/v1/maintenance/contracts/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_contracts"] >= 1


def test_list_contracts_filter_by_service_type(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    elevator_contractor = _create_contractor(client, headers, specialty="elevator")
    hvac_contractor = _create_contractor(client, headers, specialty="hvac")
    _create_contract(client, headers, property_id, elevator_contractor, service_type="elevator")
    _create_contract(client, headers, property_id, hvac_contractor, service_type="hvac")

    resp = client.get("/api/v1/maintenance/contracts", params={"service_type": "elevator"}, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["service_type"] == "elevator"


# ---------------- Permissions ----------------
def test_maintenance_contracts_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/maintenance/contracts")
    assert resp.status_code == 401


def test_existing_maintenance_requests_unaffected(client, seeded_admin):
    """Regression guard: creating a plain (non-contract-linked) maintenance
    request still works exactly as before this extension — the new
    maintenance_contract_id column is optional and defaults to null."""
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/maintenance/requests", json={
        "property_id": property_id, "title": "Unrelated leak", "category": "plumbing",
        "priority": "medium", "reported_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json().get("maintenance_contract_id") is None


def test_link_request_to_contract_and_filter_by_it(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    contractor_id = _create_contractor(client, headers)
    contract = _create_contract(client, headers, property_id, contractor_id)
    client.post(f"/api/v1/maintenance/contracts/{contract['id']}/activate", headers=headers)

    linked = client.post("/api/v1/maintenance/requests", json={
        "property_id": property_id, "title": "Elevator making noise", "category": "elevator",
        "priority": "high", "reported_date": str(date.today()), "maintenance_contract_id": contract["id"],
    }, headers=headers)
    assert linked.status_code == 201
    assert linked.json()["maintenance_contract_id"] == contract["id"]

    client.post("/api/v1/maintenance/requests", json={
        "property_id": property_id, "title": "Unrelated leak", "category": "plumbing",
        "priority": "medium", "reported_date": str(date.today()),
    }, headers=headers)

    resp = client.get("/api/v1/maintenance/requests", params={"maintenance_contract_id": contract["id"]}, headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == linked.json()["id"]


def test_invalid_maintenance_contract_id_rejected_on_request(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/maintenance/requests", json={
        "property_id": property_id, "title": "Bad link", "category": "elevator",
        "priority": "medium", "reported_date": str(date.today()), "maintenance_contract_id": 999999,
    }, headers=headers)
    assert resp.status_code == 400
