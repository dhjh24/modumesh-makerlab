"""Metrics endpoint tests (GM-12 D4.1).

GET /api/v1/metrics serves Prometheus text format, exposes the GM-12 metric
families, and enforces the optional API_METRICS_TOKEN bearer when configured.
Gauge refresh is defensive: with no live Redis/Postgres in unit tests the
scrape still succeeds with zeroed gauges.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


class TestMetricsEndpoint:
    def test_metrics_serves_prometheus_text(self) -> None:
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert "# HELP" in body

    def test_http_request_counter_family_present(self) -> None:
        body = client.get("/api/v1/metrics").text
        assert "modumesh_http_requests_total" in body

    def test_job_submissions_counter_family_present(self) -> None:
        body = client.get("/api/v1/metrics").text
        assert "modumesh_job_submissions_total" in body

    def test_plugin_duration_histogram_family_present(self) -> None:
        body = client.get("/api/v1/metrics").text
        assert "modumesh_plugin_execution_duration_seconds" in body

    def test_scrape_gauges_families_present(self) -> None:
        # Without live deps the gauges are zeroed but the families must exist.
        body = client.get("/api/v1/metrics").text
        assert "modumesh_queue_depth" in body
        assert "modumesh_active_leases" in body
        assert "modumesh_job_terminal" in body

    def test_request_metrics_are_collected(self) -> None:
        # Issue a request first, then confirm the counter for that route+status.
        client.get("/api/v1/health/live")
        body = client.get("/api/v1/metrics").text
        assert 'modumesh_http_requests_total{method="GET",route="/health/live",status="200"}' in body

    def test_metrics_token_required_when_configured(self, monkeypatch) -> None:
        # pytest auto-undoes the patch after the test; no manual cleanup.
        monkeypatch.setattr(settings.api, "metrics_token", "test-token-123")
        assert client.get("/api/v1/metrics").status_code == 401
        ok = client.get(
            "/api/v1/metrics",
            headers={"Authorization": "Bearer test-token-123"},
        )
        assert ok.status_code == 200
        assert ok.text
        bad = client.get(
            "/api/v1/metrics",
            headers={"Authorization": "Bearer wrong"},
        )
        assert bad.status_code == 401
