"""Phase 2 integration tests — PostgreSQL + Redis + Worker + MinIO.

Run against a live Docker Compose stack after migrations:

    make smoke
    # or
    pytest apps/api/tests/test_phase2_integration.py -v
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest

API_BASE = "http://localhost:8000"
TIMEOUT = 10.0


def _client() -> httpx.Client:
    return httpx.Client(base_url=API_BASE, timeout=TIMEOUT)


def _wait_job(
    client: httpx.Client,
    job_id: str,
    *,
    terminal: set[str] | None = None,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    terminal = terminal or {"completed", "failed", "cancelled"}
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        resp = client.get(f"/api/v1/jobs/{job_id}/progress")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in terminal:
            return last
        time.sleep(0.4)
    raise AssertionError(f"Job {job_id} did not reach {terminal}; last={last}")


@pytest.fixture(scope="module")
def api() -> httpx.Client:
    with _client() as client:
        # Fail fast if stack is down
        live = client.get("/health/live")
        assert live.status_code == 200
        yield client


class TestProjects:
    def test_create_list_get_update_archive(self, api: httpx.Client) -> None:
        created = api.post(
            "/api/v1/projects",
            json={"name": "Phase2 Demo", "description": "integration"},
        )
        assert created.status_code == 201
        project = created.json()
        assert project["name"] == "Phase2 Demo"
        assert project["status"] == "active"
        project_id = project["id"]

        listed = api.get("/api/v1/projects")
        assert listed.status_code == 200
        assert listed.json()["total"] >= 1
        assert any(p["id"] == project_id for p in listed.json()["items"])

        got = api.get(f"/api/v1/projects/{project_id}")
        assert got.status_code == 200
        assert got.json()["id"] == project_id

        updated = api.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Phase2 Demo Updated"},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Phase2 Demo Updated"

        archived = api.post(f"/api/v1/projects/{project_id}/archive")
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["archived_at"] is not None

        # Creating jobs on archived project must fail
        job = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={"job_type": "sample", "input_payload": {}},
        )
        assert job.status_code == 409


class TestSampleJobHappyPath:
    def test_sample_job_completes_with_downloadable_checksummed_file(
        self, api: httpx.Client
    ) -> None:
        project = api.post(
            "/api/v1/projects",
            json={"name": "Job Happy Path"},
        ).json()
        project_id = project["id"]

        create = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={
                "job_type": "sample",
                "input_payload": {"hello": "world"},
                "timeout_seconds": 60,
            },
        )
        assert create.status_code == 201
        job = create.json()
        assert job["status"] in ("created", "queued", "running", "completed")
        job_id = job["id"]

        final = _wait_job(api, job_id)
        assert final["status"] == "completed", final
        assert final["progress_pct"] == 100

        detail = api.get(f"/api/v1/jobs/{job_id}").json()
        assert detail["status"] == "completed"

        files = api.get(f"/api/v1/jobs/{job_id}/files")
        assert files.status_code == 200
        file_items = files.json()["items"]
        assert len(file_items) == 1
        file_obj = file_items[0]
        assert file_obj["sha256"]
        assert len(file_obj["sha256"]) == 64
        assert file_obj["object_key"].startswith(f"projects/{project_id}/jobs/{job_id}/")

        download = api.get(f"/api/v1/files/{file_obj['id']}/download")
        assert download.status_code == 200
        assert download.headers.get("X-Checksum-SHA256") == file_obj["sha256"]
        assert b"sample artifact" in download.content.lower() or b"Phase 2" in download.content

        # Project file listing includes the artifact
        project_files = api.get(f"/api/v1/projects/{project_id}/files").json()
        assert any(f["id"] == file_obj["id"] for f in project_files["items"])


class TestIdempotency:
    def test_duplicate_idempotency_key_returns_same_job(
        self, api: httpx.Client
    ) -> None:
        project_id = api.post(
            "/api/v1/projects", json={"name": "Idempotency"}
        ).json()["id"]

        headers = {"Idempotency-Key": "idem-key-phase2-001"}
        body = {"job_type": "sample", "input_payload": {"n": 1}}

        first = api.post(
            f"/api/v1/projects/{project_id}/jobs", json=body, headers=headers
        )
        assert first.status_code == 201
        second = api.post(
            f"/api/v1/projects/{project_id}/jobs", json=body, headers=headers
        )
        assert second.status_code == 200
        assert second.headers.get("Idempotent-Replayed") == "true"
        assert first.json()["id"] == second.json()["id"]

        # History should contain exactly one job for this key
        jobs = api.get(f"/api/v1/projects/{project_id}/jobs").json()
        matching = [
            j for j in jobs["items"] if j.get("idempotency_key") == "idem-key-phase2-001"
        ]
        assert len(matching) == 1


class TestCancellation:
    def test_cancel_queued_or_running_job(self, api: httpx.Client) -> None:
        project_id = api.post(
            "/api/v1/projects", json={"name": "Cancel Test"}
        ).json()["id"]

        created = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={
                "job_type": "sample",
                "input_payload": {"force_sleep_seconds": 5},
                "timeout_seconds": 60,
            },
        )
        assert created.status_code == 201
        job_id = created.json()["id"]

        # Give worker a moment to claim, then cancel
        time.sleep(0.8)
        cancel = api.post(f"/api/v1/jobs/{job_id}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["cancel_requested"] is True or cancel.json()["status"] == "cancelled"

        final = _wait_job(api, job_id, terminal={"cancelled", "completed", "failed"})
        # Prefer cancelled; if the job finished first that's still a valid race —
        # but with 8s sleep it should cancel.
        assert final["status"] == "cancelled", final


class TestRetry:
    def test_retry_creates_linked_attempt(self, api: httpx.Client) -> None:
        project_id = api.post(
            "/api/v1/projects", json={"name": "Retry Test"}
        ).json()["id"]

        # Force timeout → failed
        created = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={
                "job_type": "sample",
                "input_payload": {"force_sleep_seconds": 4},
                "timeout_seconds": 1,
            },
        )
        assert created.status_code == 201
        job_id = created.json()["id"]

        failed = _wait_job(api, job_id, terminal={"failed", "cancelled", "completed"}, timeout_s=30)
        assert failed["status"] == "failed", failed

        retry = api.post(f"/api/v1/jobs/{job_id}/retry")
        assert retry.status_code == 201
        new_job = retry.json()
        assert new_job["id"] != job_id
        assert new_job["parent_job_id"] == job_id
        assert new_job["attempt_number"] == 2

        # Cancel the retry so we don't leave long jobs hanging (it inherits sleep)
        api.post(f"/api/v1/jobs/{new_job['id']}/cancel")
        _wait_job(api, new_job["id"], terminal={"cancelled", "completed", "failed"})


class TestTimeout:
    def test_forced_timeout_marks_failed(self, api: httpx.Client) -> None:
        project_id = api.post(
            "/api/v1/projects", json={"name": "Timeout Test"}
        ).json()["id"]

        created = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={
                "job_type": "sample",
                "input_payload": {"force_sleep_seconds": 4},
                "timeout_seconds": 1,
            },
        )
        job_id = created.json()["id"]
        final = _wait_job(api, job_id, timeout_s=30)
        assert final["status"] == "failed"
        detail = api.get(f"/api/v1/jobs/{job_id}").json()
        assert "timeout" in (detail.get("error_message") or "").lower()


class TestDurability:
    def test_project_and_job_history_readable_after_ops(
        self, api: httpx.Client
    ) -> None:
        """Records persist in PostgreSQL and remain readable via API."""
        project_id = api.post(
            "/api/v1/projects", json={"name": "Durable Project"}
        ).json()["id"]
        job_id = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={"job_type": "sample", "input_payload": {"persist": True}},
        ).json()["id"]
        _wait_job(api, job_id)

        # Re-read after completion — survives independent of in-memory worker state
        project = api.get(f"/api/v1/projects/{project_id}")
        assert project.status_code == 200
        jobs = api.get(f"/api/v1/projects/{project_id}/jobs")
        assert jobs.status_code == 200
        assert any(j["id"] == job_id for j in jobs.json()["items"])


class TestInvalidJobType:
    def test_rejects_non_sample_job_type(self, api: httpx.Client) -> None:
        project_id = api.post(
            "/api/v1/projects", json={"name": "Bad Type"}
        ).json()["id"]
        resp = api.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={"job_type": "cadquery", "input_payload": {}},
        )
        assert resp.status_code == 400


class TestLeaseReaper:
    def test_expired_lease_is_marked_failed(self, api: httpx.Client) -> None:
        """Plant an abandoned leased job; worker reaper should mark it failed."""
        import asyncio
        import uuid as uuid_lib
        from datetime import datetime, timedelta, timezone

        from app.database import async_session_factory
        from app.models import GenerationJob, Project
        from app.services.projects import ensure_default_owner

        project_id = api.post(
            "/api/v1/projects", json={"name": "Lease Reaper"}
        ).json()["id"]
        project_uuid = uuid_lib.UUID(project_id)
        abandoned_id = uuid_lib.uuid4()

        async def plant_abandoned_job() -> None:
            async with async_session_factory() as session:
                await ensure_default_owner(session)
                project = await session.get(Project, project_uuid)
                assert project is not None
                now = datetime.now(timezone.utc)
                session.add(
                    GenerationJob(
                        id=abandoned_id,
                        project_id=project_uuid,
                        job_type="sample",
                        status="running",
                        input_payload={"planted": True},
                        progress_pct=25,
                        progress_message="abandoned mid-run",
                        attempt_number=1,
                        worker_id="dead-worker-test",
                        lease_expires_at=now - timedelta(seconds=10),
                        heartbeat_at=now - timedelta(seconds=40),
                        timeout_seconds=120,
                        cancel_requested=False,
                        started_at=now - timedelta(seconds=40),
                        created_at=now - timedelta(seconds=40),
                        updated_at=now - timedelta(seconds=40),
                        queued_at=now - timedelta(seconds=40),
                    )
                )
                await session.commit()

        asyncio.run(plant_abandoned_job())

        # Worker reaper interval is ~15s
        final = _wait_job(api, str(abandoned_id), timeout_s=45)
        assert final["status"] == "failed", final
        detail = api.get(f"/api/v1/jobs/{abandoned_id}").json()
        assert "lease" in (detail.get("error_message") or "").lower()
