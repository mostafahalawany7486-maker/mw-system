"""
Notification endpoint tests. Found to have zero test coverage during the
production audit despite NotificationService/the /notifications router
being fully implemented and already in active use (e.g. rental contract
renewal reminders). Also covers the specific edge case the audit's
list-capping fix had to get right: mark-all-read must clear every unread
notification, not just the ones a capped list would display.
"""
from app.models.system import Notification
from app.core.security import hash_password
from app.models.user import User


def _auth_headers(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed_notifications(db_session, user_id: int, count: int, unread: bool = True):
    for i in range(count):
        db_session.add(Notification(
            recipient_id=user_id, title=f"Test notification {i}", message="Body text",
            notification_type="info", is_read=not unread,
        ))
    db_session.commit()


def test_unread_count_reflects_seeded_notifications(client, seeded_admin, db_session):
    headers = _auth_headers(client)
    _seed_notifications(db_session, seeded_admin.id, count=3)

    resp = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 3


def test_list_notifications_returns_seeded_items(client, seeded_admin, db_session):
    headers = _auth_headers(client)
    _seed_notifications(db_session, seeded_admin.id, count=2)

    resp = client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert all("title" in n and "message" in n for n in body)


def test_list_notifications_is_capped(client, seeded_admin, db_session):
    """The display list is capped at 50 (see NotificationRepository.
    list_for_user's default limit) — found unbounded during the audit,
    since a long-tenured user's notification history has no natural
    upper size and this endpoint is called every time the bell dropdown
    opens."""
    headers = _auth_headers(client)
    _seed_notifications(db_session, seeded_admin.id, count=60)

    resp = client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 50


def test_list_unread_only_filter(client, seeded_admin, db_session):
    headers = _auth_headers(client)
    _seed_notifications(db_session, seeded_admin.id, count=2, unread=True)
    _seed_notifications(db_session, seeded_admin.id, count=3, unread=False)

    resp = client.get("/api/v1/notifications", params={"unread_only": True}, headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_mark_notification_read(client, seeded_admin, db_session):
    headers = _auth_headers(client)
    _seed_notifications(db_session, seeded_admin.id, count=1)
    notif_id = db_session.query(Notification).filter(Notification.recipient_id == seeded_admin.id).first().id

    resp = client.post(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert resp.status_code == 200

    unread = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert unread.json()["unread_count"] == 0


def test_mark_notification_read_ignores_other_users_notification(client, seeded_admin, db_session):
    """A user must not be able to mark someone else's notification as read."""
    headers = _auth_headers(client)
    other_user = User(
        first_name="Other", last_name="User", email="other-notif-user@test.com",
        hashed_password=hash_password("Other@12345"), is_active=True, is_superuser=False,
    )
    db_session.add(other_user)
    db_session.commit()
    _seed_notifications(db_session, other_user.id, count=1)
    other_notif_id = db_session.query(Notification).filter(Notification.recipient_id == other_user.id).first().id

    resp = client.post(f"/api/v1/notifications/{other_notif_id}/read", headers=headers)
    assert resp.status_code == 200  # endpoint always returns success (doesn't leak existence), but...

    still_unread = db_session.query(Notification).filter(Notification.id == other_notif_id).first()
    assert still_unread.is_read is False  # ...the other user's notification must be untouched


def test_mark_all_read_clears_every_unread_notification_beyond_the_display_cap(client, seeded_admin, db_session):
    """The one scenario the audit's fix specifically had to get right:
    mark-all-read must clear ALL unread notifications, not just the 50
    most recent ones the capped list endpoint would display. Before the
    fix, capping list_for_user() without an override here would have
    silently left older unread notifications stuck forever."""
    headers = _auth_headers(client)
    _seed_notifications(db_session, seeded_admin.id, count=75, unread=True)

    resp = client.post("/api/v1/notifications/read-all", headers=headers)
    assert resp.status_code == 200
    assert "75" in resp.json()["message"]

    remaining_unread = db_session.query(Notification).filter(
        Notification.recipient_id == seeded_admin.id, Notification.is_read.is_(False),
    ).count()
    assert remaining_unread == 0


def test_notifications_require_authentication(client, seeded_admin):
    resp = client.get("/api/v1/notifications")
    assert resp.status_code == 401
    resp = client.get("/api/v1/notifications/unread-count")
    assert resp.status_code == 401
