"""Pytest fixtures.

Two tiers of test, deliberately separated (TRD 34.1):

  * Unit / API tests run with NO database. They exercise validation, hashing, RBAC and
    the error envelope, and run anywhere including CI without a service container.

  * Integration tests (`@pytest.mark.integration`) need a real PostgreSQL + PostGIS.
    SQLite is never used as a substitute - PostGIS geometry, native enums and the
    check constraints are central to this system, and SQLite would silently not
    enforce them, which is worse than not testing at all.

Integration tests SKIP (not fail) when no database is reachable, so `pytest` is always
runnable on a laptop; CI provides the service container and runs the full set.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("JWT_SECRET", "test-secret-value-not-used-outside-tests-0123456789")

from app.api.deps import get_db  # noqa: E402
from app.core.rbac import UserRole  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.user import User  # noqa: E402


def _database_available(url: str) -> bool:
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT PostGIS_Lib_Version()"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://florasentry:florasentry@localhost:55432/florasentry",
        ),
    )


@pytest.fixture(scope="session")
def db_available(database_url: str) -> bool:
    return _database_available(database_url)


@pytest.fixture
def db_session(database_url: str, db_available: bool) -> Iterator[Session]:
    """A transactional session, rolled back after each test so tests never leak state."""
    if not db_available:
        pytest.skip("No PostgreSQL/PostGIS reachable - integration test skipped")

    engine = create_engine(database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()  # nothing a test writes ever persists
        connection.close()
        engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """API client with NO database.

    Endpoints that touch the database will fail here by design; use `db_client` for
    those. This fixture proves the app boots and that routing, validation and the
    error envelope work without any infrastructure.
    """
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_client(db_session: Session) -> Iterator[TestClient]:
    """API client bound to the transactional test session."""
    app = create_app()

    def _override_get_db() -> Iterator[Session]:
        # Do not commit: the fixture's outer transaction is rolled back afterwards.
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db_session: Session):
    """Factory creating an active user of any role."""

    def _make(
        role: UserRole = UserRole.FARMER,
        password: str = "test-password-123",
        *,
        with_farmer_profile: bool = False,
    ) -> User:
        from app.models.farmer import Farmer

        suffix = uuid.uuid4().hex[:10]
        user = User(
            full_name=f"Test {role.value}",
            phone=f"+9199{suffix[:8]}",
            email=f"{role.value.lower()}-{suffix}@example.com",
            password_hash=hash_password(password),
            role=role.value,
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()

        if with_farmer_profile or role is UserRole.FARMER:
            db_session.add(Farmer(user_id=user.id))
            db_session.flush()
        return user

    return _make


@pytest.fixture
def auth_headers(db_session: Session):
    """Build an Authorization header for a given user."""

    def _headers(user: User) -> dict[str, str]:
        from app.core.security import create_access_token

        token, _ = create_access_token(user_id=user.id, role=user.role)
        return {"Authorization": f"Bearer {token}"}

    return _headers
