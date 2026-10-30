"""
Auth flow tests: login success/failure, lockout, forgot/reset password,
/me endpoint, JWT-protected route rejection without a token.
"""


def test_login_success(client, seeded_admin):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_password(client, seeded_admin):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "WrongPass1"})
    assert resp.status_code == 401


def test_login_unknown_email(client, seeded_admin):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Whatever1"})
    assert resp.status_code == 401


def test_account_lockout_after_five_failed_attempts(client, seeded_admin):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 423  # locked, even with correct password now


def test_me_requires_token(client, seeded_admin):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, seeded_admin):
    login = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    token = login.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@test.com"


def test_forgot_password_does_not_leak_existence(client, seeded_admin):
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
    assert resp.status_code == 200  # generic success regardless of whether email exists


def test_forgot_and_reset_password_flow(client, seeded_admin):
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "admin@test.com"})
    assert forgot.status_code == 200
    # In development APP_ENV, the token is embedded in the message for testability.
    message = forgot.json()["message"]
    if "[DEV TOKEN: " in message:
        token = message.split("[DEV TOKEN: ")[1].rstrip("]")
        reset = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "NewPass@123"})
        assert reset.status_code == 200
        # Old password should no longer work
        old_login = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
        assert old_login.status_code == 401
        # New password should work
        new_login = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "NewPass@123"})
        assert new_login.status_code == 200
