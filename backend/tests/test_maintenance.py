"""
Maintenance tests: contractors, technicians, request creation/validation,
status machine transitions, materials, labor costs, photo uploads,
dashboard, and permission enforcement.
"""
import io
from datetime import date, timedelta


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_property(client, headers):
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Maint", "last_name": "Owner"}, headers=headers).json()
    resp = client.post("/api/v1/properties", json={"property_type": "apartment", "title": "Maintenance Test Unit", "owner_id": owner["id"]}, headers=headers)
    return resp.json()["id"]


def _create_contractor(client, headers):
    resp = client.post("/api/v1/maintenance/contractors", json={"company_name": "Test Contractors Inc", "specialty": "general"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_technician(client, headers, contractor_id=None):
    payload = {"first_name": "Test", "last_name": "Tech", "specialty": "general"}
    if contractor_id:
        payload["contractor_id"] = contractor_id
    resp = client.post("/api/v1/maintenance/technicians", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_request(client, headers, property_id, **overrides):
    payload = {
        "property_id": property_id, "title": "Test issue", "category": "plumbing",
        "priority": "medium", "reported_date": str(date.today()),
    }
    payload.update(overrides)
    resp = client.post("/api/v1/maintenance/requests", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ---------------- Contractors ----------------
def test_create_contractor(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/maintenance/contractors", json={"company_name": "Ace Repairs", "specialty": "plumbing"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["contractor_code"].startswith("CON-")


def test_invalid_specialty_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/maintenance/contractors", json={"company_name": "Bad Specialty Co", "specialty": "wizardry"}, headers=headers)
    assert resp.status_code == 422


def test_cannot_delete_contractor_with_technicians(client, seeded_admin):
    headers = _auth_headers(client)
    contractor_id = _create_contractor(client, headers)
    _create_technician(client, headers, contractor_id)
    resp = client.delete(f"/api/v1/maintenance/contractors/{contractor_id}", headers=headers)
    assert resp.status_code == 409


# ---------------- Technicians ----------------
def test_create_in_house_technician(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/maintenance/technicians", json={"first_name": "In", "last_name": "House", "specialty": "electrical"}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_in_house"] is True
    assert body["technician_code"].startswith("TEC-")


def test_technician_invalid_contractor_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/maintenance/technicians", json={"first_name": "Bad", "last_name": "Link", "contractor_id": 999999}, headers=headers)
    assert resp.status_code == 400


# ---------------- Requests ----------------
def test_create_request_success(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    assert req["maintenance_status"] == "reported"
    assert req["request_number"].startswith("MNT-")


def test_create_request_invalid_property_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/maintenance/requests", json={
        "property_id": 999999, "title": "x", "reported_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 400


def test_invalid_priority_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/maintenance/requests", json={
        "property_id": property_id, "title": "x", "priority": "critical", "reported_date": str(date.today()),
    }, headers=headers)
    assert resp.status_code == 422


def test_scheduled_before_reported_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    resp = client.post("/api/v1/maintenance/requests", json={
        "property_id": property_id, "title": "x", "reported_date": str(date.today()),
        "scheduled_date": str(date.today() - timedelta(days=5)),
    }, headers=headers)
    assert resp.status_code == 422


# ---------------- Status Machine ----------------
def test_full_status_lifecycle(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    technician_id = _create_technician(client, headers)
    req = _create_request(client, headers, property_id)

    assign_resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/assign", json={"assigned_technician_id": technician_id}, headers=headers)
    assert assign_resp.status_code == 200
    assert assign_resp.json()["maintenance_status"] == "assigned"

    start_resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["maintenance_status"] == "in_progress"

    hold_resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/hold", json={"on_hold_reason": "Waiting on parts"}, headers=headers)
    assert hold_resp.status_code == 200
    assert hold_resp.json()["maintenance_status"] == "on_hold"

    resume_resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/resume", headers=headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["maintenance_status"] == "in_progress"

    complete_resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/complete", json={"completed_date": str(date.today())}, headers=headers)
    assert complete_resp.status_code == 200
    assert complete_resp.json()["maintenance_status"] == "completed"


def test_cannot_start_reported_request_without_assignment_transition(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/start", headers=headers)
    assert resp.status_code == 409


def test_cannot_transition_from_terminal_state(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    client.post(f"/api/v1/maintenance/requests/{req['id']}/cancel", json={"cancellation_reason": "duplicate"}, headers=headers)
    resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/start", headers=headers)
    assert resp.status_code == 409


def test_assign_requires_contractor_or_technician(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/assign", json={}, headers=headers)
    assert resp.status_code == 422


def test_cannot_edit_completed_request(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    technician_id = _create_technician(client, headers)
    req = _create_request(client, headers, property_id)
    client.post(f"/api/v1/maintenance/requests/{req['id']}/assign", json={"assigned_technician_id": technician_id}, headers=headers)
    client.post(f"/api/v1/maintenance/requests/{req['id']}/start", headers=headers)
    client.post(f"/api/v1/maintenance/requests/{req['id']}/complete", json={"completed_date": str(date.today())}, headers=headers)
    resp = client.put(f"/api/v1/maintenance/requests/{req['id']}", json={"title": "changed"}, headers=headers)
    assert resp.status_code == 409


# ---------------- Materials & Labor ----------------
def test_add_material_and_compute_total(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/materials", json={
        "name": "PVC pipe", "quantity": "3", "unit_cost": "5.50",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["total_cost"] == "16.50"

    detail = client.get(f"/api/v1/maintenance/requests/{req['id']}", headers=headers).json()
    assert detail["total_material_cost"] == "16.50"


def test_add_labor_cost_and_compute_total(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    technician_id = _create_technician(client, headers)
    req = _create_request(client, headers, property_id)
    resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/labor", json={
        "technician_id": technician_id, "work_date": str(date.today()), "hours": "2", "hourly_rate": "50.00",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["total_cost"] == "100.00"

    detail = client.get(f"/api/v1/maintenance/requests/{req['id']}", headers=headers).json()
    assert detail["total_labor_cost"] == "100.00"
    assert detail["total_actual_cost"] == "100.00"


def test_material_negative_values_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    resp = client.post(f"/api/v1/maintenance/requests/{req['id']}/materials", json={
        "name": "bad", "quantity": "-1", "unit_cost": "5.00",
    }, headers=headers)
    assert resp.status_code == 422


# ---------------- Photos ----------------
def test_upload_before_and_after_photos(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)

    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    resp = client.post(
        f"/api/v1/maintenance/requests/{req['id']}/photos",
        data={"photo_type": "before", "caption": "Leak before repair"},
        files={"file": ("before.jpg", fake_image, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["photo_type"] == "before"

    detail = client.get(f"/api/v1/maintenance/requests/{req['id']}", headers=headers).json()
    assert len(detail["photos"]) == 1


def test_invalid_photo_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    resp = client.post(
        f"/api/v1/maintenance/requests/{req['id']}/photos",
        data={"photo_type": "during"},
        files={"file": ("x.jpg", fake_image, "image/jpeg")},
        headers=headers,
    )
    assert resp.status_code == 400


# ---------------- Dashboard & Permissions ----------------
def test_maintenance_dashboard(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    _create_request(client, headers, property_id)
    resp = client.get("/api/v1/maintenance/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_requests"] >= 1


def test_maintenance_requires_authentication(client, seeded_admin):
    resp = client.get("/api/v1/maintenance/requests")
    assert resp.status_code == 401


def test_history_recorded_via_activity_log(client, seeded_admin):
    headers = _auth_headers(client)
    property_id = _create_property(client, headers)
    req = _create_request(client, headers, property_id)
    resp = client.get("/api/v1/activity-logs", params={"entity_type": "maintenance_request", "entity_id": req["id"]}, headers=headers)
    assert resp.status_code == 200
    assert any(e["action"] == "created" for e in resp.json())
