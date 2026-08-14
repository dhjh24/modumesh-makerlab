"""Phase 3 integration: plugin registry + fixture-echo job execution."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest

BASE = "http://localhost:8000"


def _admin_headers() -> dict[str, str]:
    """Bearer header for admin-only endpoints (key comes from the stack env)."""
    key = os.environ.get("ADMIN_API_KEY", "")
    return {"Authorization": f"Bearer {key}"}


def _wait_job(client: httpx.Client, job_id: str, timeout: float = 60.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        r = client.get(f"{BASE}/api/v1/jobs/{job_id}/progress")
        r.raise_for_status()
        last = r.json()
        if last["status"] in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(0.4)
    return last


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(timeout=30.0) as c:
        live = c.get(f"{BASE}/health/live")
        if live.status_code != 200:
            pytest.skip("API not reachable — start the docker stack")
        yield c


def test_plugin_appears_after_resync(client: httpx.Client):
    r = client.post(f"{BASE}/api/v1/plugins/resync", headers=_admin_headers())
    r.raise_for_status()
    body = r.json()
    assert body["discovered"] >= 1
    ids = {i["plugin_id"] for i in body["items"]}
    assert "fixture-echo" in ids

    listed = client.get(f"{BASE}/api/v1/plugins", params={"enabled_only": True})
    listed.raise_for_status()
    assert any(i["plugin_id"] == "fixture-echo" for i in listed.json()["items"])


def test_fixture_echo_job_records_version_and_outputs(client: httpx.Client):
    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase3-plugin", "description": "plugin integration"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]

    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "fixture-echo",
            "input_payload": {"message": "integration-ok", "tag": "smoke"},
            "timeout_seconds": 60,
        },
    )
    assert job.status_code == 201, job.text
    body = job.json()
    assert body["plugin_version"] == "1.0.0"
    assert body["input_payload"]["message"] == "integration-ok"

    progress = _wait_job(client, body["id"], timeout=90)
    assert progress["status"] == "completed", progress

    detail = client.get(f"{BASE}/api/v1/jobs/{body['id']}")
    detail.raise_for_status()
    assert detail.json()["plugin_version"] == "1.0.0"

    files = client.get(f"{BASE}/api/v1/jobs/{body['id']}/files")
    files.raise_for_status()
    names = {f["filename"] for f in files.json()["items"]}
    assert "echo.json" in names
    assert "note.txt" in names


def test_invalid_plugin_input_rejected(client: httpx.Client):
    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase3-bad-input"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]

    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "fixture-echo",
            "input_payload": {"unexpected": True},
            "timeout_seconds": 30,
        },
    )
    assert job.status_code == 400


def test_plugin_timeout_fails(client: httpx.Client):
    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase3-timeout"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]

    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "fixture-echo",
            "input_payload": {
                "message": "slow",
                "force_sleep_seconds": 5,
            },
            "timeout_seconds": 1,
        },
    )
    assert job.status_code == 201, job.text
    progress = _wait_job(client, job.json()["id"], timeout=30)
    assert progress["status"] == "failed"
    assert "timeout" in (progress.get("error_message") or "").lower() or "timed" in (
        progress.get("progress_message") or ""
    ).lower()


def test_disable_plugin_blocks_jobs(client: httpx.Client):
    plugin = client.get(f"{BASE}/api/v1/plugins/fixture-echo")
    plugin.raise_for_status()
    version = plugin.json()["version"]

    disabled = client.post(
        f"{BASE}/api/v1/plugins/fixture-echo/versions/{version}/disable",
        headers=_admin_headers(),
    )
    disabled.raise_for_status()
    assert disabled.json()["enabled"] is False

    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase3-disabled"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]
    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "fixture-echo",
            "input_payload": {"message": "nope"},
        },
    )
    assert job.status_code == 400

    enabled = client.post(
        f"{BASE}/api/v1/plugins/fixture-echo/versions/{version}/enable"
    )
    enabled.raise_for_status()
    assert enabled.json()["enabled"] is True
