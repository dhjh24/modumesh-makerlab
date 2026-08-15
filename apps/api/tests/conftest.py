"""Shared pytest fixtures for the API unit tests.

Unit tests exercise the real FastAPI app + real SQLAlchemy async stack against
an in-memory SQLite database (aiosqlite). The schema is hand-written SQLite
DDL because the production migrations are PostgreSQL-specific (``JSONB``,
``NOW()``, ``::jsonb`` casts do not parse on SQLite) — the ORM models map
cleanly onto it (``postgresql.UUID`` falls back to CHAR(32) on SQLite).

Rate limiting is disabled for the whole unit-test session: the middleware's
in-memory windows are shared across every TestClient request in the process,
so the 60/min default cap would make the combined suite flaky. The middleware
itself is unit-tested directly in tests/test_rate_limiting.py.
"""

from __future__ import annotations

import os

# Must be set before `app.config` is first imported — pytest imports this
# conftest before any test module, so the settings singleton sees it.
os.environ["API_RATE_LIMIT_ENABLED"] = "false"

import sqlalchemy as sa  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import auth as auth_service  # noqa: E402

# Password hashing is intentionally heavy (600k PBKDF2 iterations in prod).
# The stored format embeds the iteration count, so lowering it here keeps
# verification correct while the suite stays fast.
auth_service.PBKDF2_ITERATIONS = 1_000

# Hand-written SQLite schema — see module docstring. Keep column names/types
# in sync with app/models.py for the tables the unit tests touch.
SQLITE_DDL = """
CREATE TABLE users (
  id VARCHAR(32) PRIMARY KEY,
  external_id VARCHAR(255) UNIQUE,
  email VARCHAR(255) UNIQUE,
  password_hash VARCHAR(255),
  display_name VARCHAR(255) NOT NULL,
  is_admin BOOLEAN NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE auth_tokens (
  id VARCHAR(32) PRIMARY KEY,
  user_id VARCHAR(32) NOT NULL,
  token_hash VARCHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP,
  last_used_at TIMESTAMP
);
CREATE TABLE projects (
  id VARCHAR(32) PRIMARY KEY,
  owner_id VARCHAR(32) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  archived_at TIMESTAMP
);
CREATE TABLE files (
  id VARCHAR(32) PRIMARY KEY,
  project_id VARCHAR(32) NOT NULL,
  job_id VARCHAR(32),
  object_key VARCHAR(512) NOT NULL UNIQUE,
  filename VARCHAR(255) NOT NULL,
  content_type VARCHAR(128) NOT NULL DEFAULT 'application/octet-stream',
  size_bytes BIGINT NOT NULL,
  sha256 VARCHAR(64) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE generation_jobs (
  id VARCHAR(32) PRIMARY KEY,
  project_id VARCHAR(32) NOT NULL,
  parent_job_id VARCHAR(32),
  job_type VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  input_payload TEXT NOT NULL DEFAULT '{}',
  progress_pct INTEGER NOT NULL DEFAULT 0,
  progress_message VARCHAR(512),
  error_message TEXT,
  idempotency_key VARCHAR(255),
  attempt_number INTEGER NOT NULL DEFAULT 1,
  worker_id VARCHAR(128),
  lease_expires_at TIMESTAMP,
  heartbeat_at TIMESTAMP,
  timeout_seconds INTEGER NOT NULL DEFAULT 60,
  plugin_version VARCHAR(32),
  cancel_requested BOOLEAN NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  queued_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP
);
CREATE TABLE audit_events (
  id VARCHAR(32) PRIMARY KEY,
  entity_type VARCHAR(64) NOT NULL,
  entity_id VARCHAR(32) NOT NULL,
  action VARCHAR(64) NOT NULL,
  actor VARCHAR(255),
  details TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE plugin_registry (
  id VARCHAR(32) PRIMARY KEY,
  plugin_id VARCHAR(64) NOT NULL,
  version VARCHAR(32) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  sdk_version VARCHAR(32) NOT NULL,
  engine VARCHAR(32) NOT NULL,
  entrypoint VARCHAR(255) NOT NULL,
  categories TEXT,
  outputs TEXT,
  timeout_seconds INTEGER NOT NULL,
  memory_mb INTEGER NOT NULL,
  network_policy VARCHAR(32) NOT NULL,
  input_schema TEXT,
  manifest TEXT,
  source_path VARCHAR(512) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL,
  diagnostics TEXT,
  max_input_bytes INTEGER NOT NULL,
  max_output_bytes INTEGER NOT NULL,
  author VARCHAR(255),
  license_id VARCHAR(64),
  license_url VARCHAR(2048),
  source_url VARCHAR(2048),
  maturity VARCHAR(32),
  tags TEXT,
  thumbnail VARCHAR(255),
  capabilities TEXT,
  discovered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class TestDb:
    """Holds the per-test SQLite engine/factory."""

    def __init__(self, path, engine, factory) -> None:
        self.path = path
        self.engine = engine
        self.factory = factory


async def _create_schema(engine) -> None:
    async with engine.begin() as conn:
        for stmt in SQLITE_DDL.split(";"):
            if stmt.strip():
                await conn.execute(sa.text(stmt))
    # Close the DDL connection: it was created in this (short-lived) loop and
    # must not be reused from TestClient's portal loop. Fresh connections are
    # checked out per use from whichever loop runs the request.
    await engine.dispose()


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture()
def db_session(db_path):
    """Fresh file-backed SQLite DB per test + ``get_db`` dependency override."""
    import asyncio

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    asyncio.run(_create_schema(engine))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tdb = TestDb(db_path, engine, factory)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield tdb
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def seeded_client(db_session):
    """TestClient with a fresh DB behind it."""
    from fastapi.testclient import TestClient

    return TestClient(app)
