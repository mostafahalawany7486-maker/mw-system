"""
Test fixtures. Uses an in-memory SQLite DB so tests run fast and without
requiring a live PostgreSQL instance. Production code targets PostgreSQL
(see DATABASE_URL) but SQLite is close enough for ORM-level unit/integration
tests in Phase 1. Any dialect-specific SQL (e.g. UUID column type) is
handled generically by SQLAlchemy's cross-dialect column types.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.core.rate_limit import limiter
from app import models  # noqa: F401 ensures models are registered
from app.main import app
from app.models.user import User, Role, Permission

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture()
def db_engine():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine) -> Session:
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Rate limiting (see app/core/rate_limit.py) uses an in-memory,
    # process-global counter — it isn't reset by creating a new
    # TestClient. Nearly every test in this suite logs in at least once
    # via the shared _auth_headers() helper pattern, so leaving it
    # enabled here would make the bulk of the test suite flaky/broken
    # once the cumulative login count crosses the per-minute limit
    # within a single test run. test_rate_limiting.py re-enables it
    # explicitly to verify the limiter itself works.
    limiter.enabled = False
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    limiter.enabled = False


@pytest.fixture()
def seeded_admin(db_session):
    """Creates a minimal Administrator role + user for auth-dependent tests."""
    all_perms = [
        Permission(code="users.view", module="users", action="view"),
        Permission(code="users.create", module="users", action="create"),
        Permission(code="users.edit", module="users", action="edit"),
        Permission(code="users.delete", module="users", action="delete"),
    ]
    for p in all_perms:
        db_session.add(p)
    db_session.flush()

    role = Role(name="Administrator", description="Full access", is_system_role=True)
    role.permissions = all_perms
    db_session.add(role)
    db_session.flush()

    admin = User(
        first_name="System", last_name="Administrator", email="admin@test.com",
        hashed_password=hash_password("Admin@12345"), is_active=True, is_superuser=True, role_id=role.id,
    )
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture()
def seeded_viewer(db_session):
    """A genuinely non-superuser account with only *.view permissions
    across the modules this audit is required to verify — used to test
    that 403 is actually returned for create/edit/delete/confirm actions.

    This fixture didn't exist before the production audit — every prior
    test in this suite that needed a logged-in user used seeded_admin,
    whose is_superuser=True bypasses PermissionChecker entirely (see
    app/api/deps.py), which is *why* 403 enforcement had essentially no
    test coverage despite being applied consistently across the API."""
    view_only_codes = [
        "properties.view", "owners.view", "tenants.view", "leases.view", "rentals.view",
        "financial.view", "maintenance.view", "accounting.view", "reports.view", "roles.view",
    ]
    perms = [Permission(code=c, module=c.split(".")[0], action="view") for c in view_only_codes]
    for p in perms:
        db_session.add(p)
    db_session.flush()

    role = Role(name="Viewer", description="Read-only test role", is_system_role=False)
    role.permissions = perms
    db_session.add(role)
    db_session.flush()

    viewer = User(
        first_name="Read", last_name="Only", email="viewer@test.com",
        hashed_password=hash_password("Viewer@12345"), is_active=True, is_superuser=False, role_id=role.id,
    )
    db_session.add(viewer)
    db_session.commit()
    return viewer
