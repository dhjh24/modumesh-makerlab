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
        assert data["status"] == "ok"
        assert data["service"] == "modumesh-api"
        assert "timestamp" in data

    def test_readiness_returns_ready(self) -> None:
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

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
