"""Phase 5 integration: Nameplate CadQuery job through the full stack."""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest

BASE = "http://localhost:8000"

DEFAULT_INPUT = {
    "text": "MAKERLAB",
    "font": "DejaVuSans",
    "width_mm": 80,
    "height_mm": 30,
    "base_thickness_mm": 3,
    "text_depth_mm": 1.2,
    "mode": "raised",
    "corner_radius_mm": 2,
    "alignment": "center",
    "hole_count": 2,
    "hole_diameter_mm": 3.2,
    "edge_margin_mm": 8,
}


def _wait_job(client: httpx.Client, job_id: str, timeout: float = 180.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        r = client.get(f"{BASE}/api/v1/jobs/{job_id}/progress")
        r.raise_for_status()
        last = r.json()
        if last["status"] in {"completed", "failed", "cancelled"}:
            return last
        time.sleep(0.5)
    return last


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(timeout=60.0) as c:
        live = c.get(f"{BASE}/health/live")
        if live.status_code != 200:
            pytest.skip("API not reachable — start the docker stack")
        from tests.conftest_auth import login

        login(c)
        yield c


def test_nameplate_plugin_discovered(client: httpx.Client):
    r = client.post(f"{BASE}/api/v1/plugins/resync")
    r.raise_for_status()
    ids = {i["plugin_id"] for i in r.json()["items"]}
    assert "nameplate" in ids

    detail = client.get(f"{BASE}/api/v1/plugins/nameplate")
    detail.raise_for_status()
    body = detail.json()
    assert body["version"] == "1.0.0"
    assert body["enabled"] is True
    names = {o["name"] for o in body["outputs"]}
    assert {"model.stl", "model.step", "model.glb", "thumbnail.png", "metadata.json"} <= names


def test_nameplate_job_completes_with_all_outputs(client: httpx.Client):
    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase5-nameplate", "description": "CadQuery reference"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]

    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "nameplate",
            "input_payload": DEFAULT_INPUT,
            "timeout_seconds": 180,
        },
    )
    assert job.status_code == 201, job.text
    body = job.json()
    assert body["plugin_version"] == "1.0.0"

    progress = _wait_job(client, body["id"], timeout=180)
    assert progress["status"] == "completed", progress

    files = client.get(f"{BASE}/api/v1/jobs/{body['id']}/files")
    files.raise_for_status()
    items = files.json()["items"]
    by_name = {f["filename"]: f for f in items}
    for name in ("model.stl", "model.step", "model.glb", "thumbnail.png", "metadata.json"):
        assert name in by_name, by_name.keys()
        assert by_name[name]["size_bytes"] > 0
        assert by_name[name]["sha256"]

    # Download STL and metadata
    stl = client.get(f"{BASE}/api/v1/files/{by_name['model.stl']['id']}/download")
    assert stl.status_code == 200
    assert len(stl.content) > 1000

    meta_resp = client.get(f"{BASE}/api/v1/files/{by_name['metadata.json']['id']}/download")
    assert meta_resp.status_code == 200
    meta = meta_resp.json()
    assert meta["validation"]["passed"] is True
    assert meta["project_version"] == body["id"]
    assert meta["inputs"]["text"] == "MAKERLAB"


def test_nameplate_invalid_input_rejected(client: httpx.Client):
    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase5-bad-input"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]

    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "nameplate",
            "input_payload": {**DEFAULT_INPUT, "text": ""},
            "timeout_seconds": 30,
        },
    )
    assert job.status_code == 400


def test_nameplate_survives_stack_restart_download(client: httpx.Client):
    """Create a completed job then re-fetch project + STL (restart exercised externally)."""
    project = client.post(
        f"{BASE}/api/v1/projects",
        json={"name": "phase5-persist"},
    )
    project.raise_for_status()
    project_id = project.json()["id"]

    job = client.post(
        f"{BASE}/api/v1/projects/{project_id}/jobs",
        json={
            "job_type": "nameplate",
            "input_payload": {**DEFAULT_INPUT, "text": "PERSIST", "hole_count": 0},
            "timeout_seconds": 180,
        },
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]
    progress = _wait_job(client, job_id, timeout=180)
    assert progress["status"] == "completed", progress

    # Re-open project (simulates UI reopen after restart).
    reopened = client.get(f"{BASE}/api/v1/projects/{project_id}")
    reopened.raise_for_status()
    assert reopened.json()["id"] == project_id

    files = client.get(f"{BASE}/api/v1/jobs/{job_id}/files")
    files.raise_for_status()
    stl = next(f for f in files.json()["items"] if f["filename"] == "model.stl")
    dl = client.get(f"{BASE}/api/v1/files/{stl['id']}/download")
    assert dl.status_code == 200
    assert len(dl.content) > 1000
