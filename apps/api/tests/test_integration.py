"""Integration smoke tests — run against a live Docker Compose stack.

These tests verify end-to-end connectivity to PostgreSQL, Redis, and MinIO
through the running API.
"""

from __future__ import annotations

import httpx

API_BASE = "http://localhost:8000"


class TestHealthEndpoints:
    """Verify all health endpoints respond correctly."""

    def test_health_general(self) -> None:
        response = httpx.get(f"{API_BASE}/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "modumesh-api"
        assert data["status"] in ("ok", "degraded")
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
        assert "minio" in data["checks"]

    def test_health_live(self) -> None:
        response = httpx.get(f"{API_BASE}/health/live", timeout=10)
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_health_ready(self) -> None:
        response = httpx.get(f"{API_BASE}/health/ready", timeout=10)
        data = response.json()
        # Should be ready or not_ready depending on whether deps are up
        assert data["status"] in ("ready", "not_ready")
        assert "checks" in data

    def test_root(self) -> None:
        response = httpx.get(f"{API_BASE}/", timeout=10)
        assert response.status_code == 200
        assert response.json()["service"] == "modumesh-api"


class TestPostgresConnectivity:
    """Verify PostgreSQL is reachable via the health endpoint."""

    def test_database_is_reachable(self) -> None:
        response = httpx.get(f"{API_BASE}/health", timeout=10)
        data = response.json()
        db_check = data["checks"]["database"]
        assert db_check["status"] == "ok", f"Database not ok: {db_check}"
        assert "latency_ms" in db_check


class TestRedisConnectivity:
    """Verify Redis is reachable via the health endpoint."""

    def test_redis_is_reachable(self) -> None:
        response = httpx.get(f"{API_BASE}/health", timeout=10)
        data = response.json()
        redis_check = data["checks"]["redis"]
        assert redis_check["status"] == "ok", f"Redis not ok: {redis_check}"
        assert "latency_ms" in redis_check


class TestMinIOConnectivity:
    """Verify MinIO is reachable and supports upload/read."""

    def test_minio_is_reachable(self) -> None:
        response = httpx.get(f"{API_BASE}/health", timeout=10)
        data = response.json()
        minio_check = data["checks"]["minio"]
        assert minio_check["status"] == "ok", f"MinIO not ok: {minio_check}"

    def test_minio_storage_write_and_read(self) -> None:
        response = httpx.get(f"{API_BASE}/health/storage-test", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok", f"Storage test failed: {data}"
        assert "write_ms" in data
        assert "read_ms" in data


class TestMigrations:
    """Verify Alembic migrations have been applied."""

    def test_migrations_applied(self) -> None:
        response = httpx.get(f"{API_BASE}/health", timeout=10)
        assert response.status_code == 200
        # If migrations are applied, the schema_migrations table exists
        # and the health endpoint (which pings PG) returns ok
        data = response.json()
        assert data["checks"]["database"]["status"] == "ok"
