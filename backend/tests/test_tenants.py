"""
Tenant module tests: individual/company validation, CRUD, sub-resources,
blacklist, rating, and permission enforcement.
"""
import io


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_individual_tenant_requires_names(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Only"}, headers=headers)
    assert resp.status_code == 422


def test_create_individual_tenant_success(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/tenants", json={
        "tenant_type": "individual", "first_name": "Alice", "last_name": "Tenant",
        "national_id": "NID-001", "passport_number": "PP-001",
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["display_name"] == "Alice Tenant"
    assert body["tenant_code"].startswith("TNT-")
    assert body["is_blacklisted"] is False


def test_create_company_tenant_requires_company_name(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/tenants", json={"tenant_type": "company"}, headers=headers)
    assert resp.status_code == 422


def test_create_company_tenant_success(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/tenants", json={
        "tenant_type": "company", "company_name": "Acme Logistics",
        "commercial_registration_number": "CR-999",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["display_name"] == "Acme Logistics"


def test_invalid_tenant_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/tenants", json={"tenant_type": "nonprofit", "company_name": "X"}, headers=headers)
    assert resp.status_code == 422


def test_duplicate_national_id_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    payload = {"tenant_type": "individual", "first_name": "Dup", "last_name": "Test", "national_id": "SAME-ID"}
    first = client.post("/api/v1/tenants", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/tenants", json={**payload, "first_name": "Dup2"}, headers=headers)
    assert second.status_code == 409


def test_list_and_search_tenants(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Searchable", "last_name": "Person"}, headers=headers)
    resp = client.get("/api/v1/tenants?search=Searchable", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_filter_tenants_by_type(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/tenants", json={"tenant_type": "company", "company_name": "FilterCo Tenant"}, headers=headers)
    resp = client.get("/api/v1/tenants?tenant_type=company", headers=headers)
    assert resp.status_code == 200
    assert all(item["tenant_type"] == "company" for item in resp.json()["items"])


def test_update_tenant(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Before", "last_name": "Update"}, headers=headers).json()
    resp = client.put(f"/api/v1/tenants/{created['id']}", json={"first_name": "After"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "After"


def test_delete_tenant_soft_deletes(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "ToDelete", "last_name": "Tenant"}, headers=headers).json()
    resp = client.delete(f"/api/v1/tenants/{created['id']}", headers=headers)
    assert resp.status_code == 200
    get_resp = client.get(f"/api/v1/tenants/{created['id']}", headers=headers)
    assert get_resp.status_code == 404


# ---------------- Blacklist ----------------
def test_blacklist_tenant(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Bad", "last_name": "Actor"}, headers=headers).json()
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": "Property damage"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_blacklisted"] is True
    assert resp.json()["blacklist_reason"] == "Property damage"


def test_blacklist_requires_reason(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Bad2", "last_name": "Actor"}, headers=headers).json()
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": ""}, headers=headers)
    assert resp.status_code == 422


def test_cannot_blacklist_twice(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Bad3", "last_name": "Actor"}, headers=headers).json()
    client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": "First"}, headers=headers)
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": "Second"}, headers=headers)
    assert resp.status_code == 409


def test_unblacklist_tenant(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Reformed", "last_name": "Tenant"}, headers=headers).json()
    client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": "test"}, headers=headers)
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/unblacklist", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_blacklisted"] is False
    assert resp.json()["blacklist_reason"] is None


def test_filter_by_blacklist_status(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Filter", "last_name": "Blacklist"}, headers=headers).json()
    client.post(f"/api/v1/tenants/{tenant['id']}/blacklist", json={"reason": "test"}, headers=headers)
    resp = client.get("/api/v1/tenants?is_blacklisted=true", headers=headers)
    assert resp.status_code == 200
    assert any(t["id"] == tenant["id"] for t in resp.json()["items"])


# ---------------- Ratings ----------------
def test_add_rating(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Rated", "last_name": "Tenant"}, headers=headers).json()
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/ratings", json={"rating_value": 4, "comment": "Good tenant"}, headers=headers)
    assert resp.status_code == 201
    detail = client.get(f"/api/v1/tenants/{tenant['id']}", headers=headers).json()
    assert detail["average_rating"] == 4.0
    assert detail["rating_count"] == 1


def test_invalid_rating_value_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Bad", "last_name": "Rating"}, headers=headers).json()
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/ratings", json={"rating_value": 6}, headers=headers)
    assert resp.status_code == 422


def test_average_rating_across_multiple_entries(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Multi", "last_name": "Rated"}, headers=headers).json()
    client.post(f"/api/v1/tenants/{tenant['id']}/ratings", json={"rating_value": 5}, headers=headers)
    client.post(f"/api/v1/tenants/{tenant['id']}/ratings", json={"rating_value": 3}, headers=headers)
    detail = client.get(f"/api/v1/tenants/{tenant['id']}", headers=headers).json()
    assert detail["average_rating"] == 4.0
    assert detail["rating_count"] == 2


# ---------------- Sub-resources ----------------
def test_add_contact_to_tenant(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "company", "company_name": "ContactTest Co"}, headers=headers).json()
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/contacts", json={"full_name": "Jordan Lee", "designation": "CFO"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["full_name"] == "Jordan Lee"


def test_add_emergency_contact(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Emergency", "last_name": "Test"}, headers=headers).json()
    resp = client.post(f"/api/v1/tenants/{tenant['id']}/emergency-contacts", json={
        "full_name": "Jane Doe", "relationship_type": "sister", "phone": "+1-555-0100",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["relationship_type"] == "sister"


def test_only_one_primary_emergency_contact(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Multi", "last_name": "Emergency"}, headers=headers).json()
    client.post(f"/api/v1/tenants/{tenant['id']}/emergency-contacts", json={"full_name": "First", "phone": "1", "is_primary": True}, headers=headers)
    client.post(f"/api/v1/tenants/{tenant['id']}/emergency-contacts", json={"full_name": "Second", "phone": "2", "is_primary": True}, headers=headers)
    detail = client.get(f"/api/v1/tenants/{tenant['id']}", headers=headers).json()
    primaries = [c for c in detail["emergency_contacts"] if c["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["full_name"] == "Second"


def test_upload_tenant_document(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Doc", "last_name": "Tenant"}, headers=headers).json()
    file_content = io.BytesIO(b"%PDF-1.4 fake national id scan")
    resp = client.post(
        f"/api/v1/tenants/{tenant['id']}/documents",
        data={"document_type": "national_id", "document_number": "NID-999"},
        files={"file": ("id.pdf", file_content, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["document_type"] == "national_id"


def test_upload_document_rejects_disallowed_extension(client, seeded_admin):
    headers = _auth_headers(client)
    tenant = client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Bad", "last_name": "File"}, headers=headers).json()
    file_content = io.BytesIO(b"not an exe really")
    resp = client.post(
        f"/api/v1/tenants/{tenant['id']}/documents",
        data={"document_type": "other"},
        files={"file": ("malware.exe", file_content, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400


# ---------------- Dashboard & permissions ----------------
def test_tenant_dashboard_summary(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/tenants", json={"tenant_type": "individual", "first_name": "Dash", "last_name": "Board"}, headers=headers)
    resp = client.get("/api/v1/tenants/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_tenants"] >= 1


def test_tenants_require_permission(client, seeded_admin):
    resp = client.get("/api/v1/tenants")
    assert resp.status_code == 401
