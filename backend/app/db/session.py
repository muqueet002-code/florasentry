"""Database engine and session management (TRD 6.6).

One transaction per request: `get_db` commits on success and rolls back on any raised
exception.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT_SEC,
    pool_pre_ping=True,  # drop dead connections instead of failing a request
    echo=settings.DATABASE_ECHO,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_statement_timeout(dbapi_conn, _record) -> None:  # type: ignore[no-untyped-def]
    """Bound every statement so a slow query returns 504 rather than hanging (TRD 9.5)."""
    if settings.DATABASE_STATEMENT_TIMEOUT_MS > 0:
        with dbapi_conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {settings.DATABASE_STATEMENT_TIMEOUT_MS}")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: request-scoped session with commit/rollback semantics."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Same semantics as `get_db`, for scripts and worker jobs."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> tuple[bool, str | None]:
    """Liveness probe for /health. Returns (ok, error_message)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.error("database_healthcheck_failed", extra={"error": type(exc).__name__})
        return False, type(exc).__name__


def check_postgis() -> tuple[bool, str | None]:
    """Confirm the PostGIS extension is installed and report its version."""
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT PostGIS_Lib_Version()")).scalar_one()
        return True, str(version)
    except Exception as exc:
        logger.error("postgis_healthcheck_failed", extra={"error": type(exc).__name__})
        return False, None
