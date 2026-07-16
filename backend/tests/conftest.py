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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


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
