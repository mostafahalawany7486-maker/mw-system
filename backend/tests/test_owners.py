"""
Owner module tests: individual/company validation, CRUD, sub-resources
(addresses, bank accounts, contacts), and permission enforcement.
"""
import io


def _login(client, email="admin@test.com", password="Admin@12345"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_headers(client):
    return {"Authorization": f"Bearer {_login(client)}"}


def test_create_individual_owner_requires_first_and_last_name(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Only"}, headers=headers)
    assert resp.status_code == 422  # last_name missing


def test_create_individual_owner_success(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/owners", json={
        "owner_type": "individual", "first_name": "Alice", "last_name": "Owner",
        "primary_email": "alice.owner@test.com",
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner_type"] == "individual"
    assert body["display_name"] == "Alice Owner"
    assert body["owner_code"].startswith("OWN-")


def test_create_company_owner_requires_company_name(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/owners", json={"owner_type": "company"}, headers=headers)
    assert resp.status_code == 422


def test_create_company_owner_success(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/owners", json={
        "owner_type": "company", "company_name": "Acme Holdings",
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["display_name"] == "Acme Holdings"


def test_invalid_owner_type_rejected(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/owners", json={"owner_type": "nonprofit", "company_name": "X"}, headers=headers)
    assert resp.status_code == 422


def test_list_and_search_owners(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Searchable", "last_name": "Person"}, headers=headers)
    resp = client.get("/api/v1/owners?search=Searchable", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any("Searchable" in item["display_name"] for item in body["items"])


def test_filter_owners_by_type(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/owners", json={"owner_type": "company", "company_name": "FilterCo"}, headers=headers)
    resp = client.get("/api/v1/owners?owner_type=company", headers=headers)
    assert resp.status_code == 200
    assert all(item["owner_type"] == "company" for item in resp.json()["items"])


def test_update_owner(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Before", "last_name": "Update"}, headers=headers).json()
    resp = client.put(f"/api/v1/owners/{created['id']}", json={"first_name": "After"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "After"


def test_delete_owner_soft_deletes(client, seeded_admin):
    headers = _auth_headers(client)
    created = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "ToDelete", "last_name": "Owner"}, headers=headers).json()
    resp = client.delete(f"/api/v1/owners/{created['id']}", headers=headers)
    assert resp.status_code == 200
    get_resp = client.get(f"/api/v1/owners/{created['id']}", headers=headers)
    assert get_resp.status_code == 404


def test_owner_not_found(client, seeded_admin):
    headers = _auth_headers(client)
    resp = client.get("/api/v1/owners/999999", headers=headers)
    assert resp.status_code == 404


# ---------------- Sub-resources ----------------
def test_add_address_to_owner(client, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Addr", "last_name": "Owner"}, headers=headers).json()
    resp = client.post(f"/api/v1/owners/{owner['id']}/addresses", json={"line1": "123 Main St", "is_primary": True}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["is_primary"] is True


def test_only_one_primary_address(client, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Multi", "last_name": "Addr"}, headers=headers).json()
    client.post(f"/api/v1/owners/{owner['id']}/addresses", json={"line1": "First St", "is_primary": True}, headers=headers)
    client.post(f"/api/v1/owners/{owner['id']}/addresses", json={"line1": "Second St", "is_primary": True}, headers=headers)
    detail = client.get(f"/api/v1/owners/{owner['id']}", headers=headers).json()
    primary_addresses = [a for a in detail["addresses"] if a["is_primary"]]
    assert len(primary_addresses) == 1
    assert primary_addresses[0]["line1"] == "Second St"


def test_add_bank_account(client, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "company", "company_name": "BankTest Co"}, headers=headers).json()
    resp = client.post(f"/api/v1/owners/{owner['id']}/bank-accounts", json={
        "bank_name": "Test Bank", "account_holder_name": "BankTest Co", "iban": "GB00TEST00000000000000",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["bank_name"] == "Test Bank"


def test_add_contact(client, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "company", "company_name": "ContactTest Co"}, headers=headers).json()
    resp = client.post(f"/api/v1/owners/{owner['id']}/contacts", json={"full_name": "Jordan Lee", "designation": "CFO"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["full_name"] == "Jordan Lee"


def test_upload_document(client, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Doc", "last_name": "Owner"}, headers=headers).json()
    file_content = io.BytesIO(b"%PDF-1.4 fake pdf content")
    resp = client.post(
        f"/api/v1/owners/{owner['id']}/documents",
        data={"document_type": "id_card", "document_number": "ID-999"},
        files={"file": ("id.pdf", file_content, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["document_type"] == "id_card"


def test_upload_document_rejects_disallowed_extension(client, seeded_admin):
    headers = _auth_headers(client)
    owner = client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Bad", "last_name": "File"}, headers=headers).json()
    file_content = io.BytesIO(b"not really an exe")
    resp = client.post(
        f"/api/v1/owners/{owner['id']}/documents",
        data={"document_type": "other"},
        files={"file": ("malware.exe", file_content, "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_owner_dashboard_summary(client, seeded_admin):
    headers = _auth_headers(client)
    client.post("/api/v1/owners", json={"owner_type": "individual", "first_name": "Dash", "last_name": "Board"}, headers=headers)
    resp = client.get("/api/v1/owners/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_owners"] >= 1


def test_owners_require_permission(client, seeded_admin):
    resp = client.get("/api/v1/owners")
    assert resp.status_code == 401
