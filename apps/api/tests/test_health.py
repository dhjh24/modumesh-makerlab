"""API test suite."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealth:
    def test_health_returns_ok(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "modumesh-api"
        assert data["status"] == "degraded"  # no deps in unit test
        assert "checks" in data

    def test_readiness_returns_not_ready(self) -> None:
        """Without real deps, readiness should return 503."""
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_liveness_returns_alive(self) -> None:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_root_returns_service_info(self) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "modumesh-api"
        assert "version" in data

    def test_correlation_id_header(self) -> None:
        response = client.get("/health", headers={"X-Correlation-ID": "test-correlation-id"})
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == "test-correlation-id"

    def test_correlation_id_generated(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        cid = response.headers.get("X-Correlation-ID")
        assert cid is not None
        assert len(cid) > 0
