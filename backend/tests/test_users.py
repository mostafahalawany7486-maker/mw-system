def _login(client, email="admin@test.com", password="Admin@12345"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_create_user_requires_permission(client, seeded_admin):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/users", json={
        "first_name": "Jane", "last_name": "Doe", "email": "jane@test.com", "password": "Passw0rd!",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["email"] == "jane@test.com"


def test_create_user_duplicate_email_conflict(client, seeded_admin):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"first_name": "Jane", "last_name": "Doe", "email": "jane@test.com", "password": "Passw0rd!"}
    first = client.post("/api/v1/users", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/v1/users", json=payload, headers=headers)
    assert second.status_code == 409


def test_list_users_pagination(client, seeded_admin):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/users?page=1&page_size=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body and "total_pages" in body


def test_deactivate_and_reactivate_user(client, seeded_admin):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/v1/users", json={
        "first_name": "Bob", "last_name": "Smith", "email": "bob@test.com", "password": "Passw0rd!",
    }, headers=headers).json()

    deactivate = client.post(f"/api/v1/users/{created['id']}/deactivate", headers=headers)
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    activate = client.post(f"/api/v1/users/{created['id']}/activate", headers=headers)
    assert activate.status_code == 200
    assert activate.json()["is_active"] is True


def test_unauthenticated_request_rejected(client, seeded_admin):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401
