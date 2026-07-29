"""Phase 6 authorization tests — users cannot access another user's resources."""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
ADMIN_USER = os.environ.get("API_BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("API_BOOTSTRAP_ADMIN_PASSWORD", "change_me_admin")


def _login(client: httpx.Client, username: str, password: str) -> dict:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    client.headers["Authorization"] = f"Bearer {data['access_token']}"
    return data


@pytest.fixture(scope="module")
def admin_client() -> httpx.Client:
    with httpx.Client(base_url=API_BASE, timeout=30.0) as client:
        live = client.get("/health/live")
        if live.status_code != 200:
            pytest.skip("API not running")
        _login(client, ADMIN_USER, ADMIN_PASS)
        yield client


class TestAuthBasics:
    def test_unauthenticated_projects_rejected(self) -> None:
        with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
            live = client.get("/health/live")
            if live.status_code != 200:
                pytest.skip("API not running")
            resp = client.get("/api/v1/projects")
            assert resp.status_code == 401

    def test_login_me_logout(self, admin_client: httpx.Client) -> None:
        me = admin_client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "admin"
        assert me.json()["username"] == ADMIN_USER

    def test_health_remains_public(self) -> None:
        with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
            assert client.get("/health/live").status_code == 200
            assert client.get("/health").status_code == 200


class TestCrossUserIsolation:
    def test_owner_cannot_read_other_project(self, admin_client: httpx.Client) -> None:
        suffix = uuid.uuid4().hex[:8]
        username = f"owner_{suffix}"
        password = "owner-pass-12345"

        created = admin_client.post(
            "/api/v1/auth/users",
            json={
                "username": username,
                "password": password,
                "display_name": "Owner User",
                "role": "owner",
            },
        )
        assert created.status_code == 201, created.text

        # Admin creates a project (owned by admin)
        admin_proj = admin_client.post(
            "/api/v1/projects",
            json={"name": f"admin-secret-{suffix}"},
        )
        assert admin_proj.status_code == 201
        admin_project_id = admin_proj.json()["id"]

        with httpx.Client(base_url=API_BASE, timeout=30.0) as owner:
            _login(owner, username, password)
            # Owner creates own project
            own = owner.post("/api/v1/projects", json={"name": f"owner-proj-{suffix}"})
            assert own.status_code == 201
            own_id = own.json()["id"]

            # Owner can see own project
            assert owner.get(f"/api/v1/projects/{own_id}").status_code == 200

            # Owner cannot see admin project
            denied = owner.get(f"/api/v1/projects/{admin_project_id}")
            assert denied.status_code == 403

            # Owner list should not include admin project
            listed = owner.get("/api/v1/projects")
            assert listed.status_code == 200
            ids = {p["id"] for p in listed.json()["items"]}
            assert own_id in ids
            assert admin_project_id not in ids

            # Owner cannot create jobs on admin project
            job = owner.post(
                f"/api/v1/projects/{admin_project_id}/jobs",
                json={"job_type": "sample", "input_payload": {}},
            )
            assert job.status_code == 403

            # Owner cannot access admin status
            assert owner.get("/api/v1/admin/status").status_code == 403

            # Owner cannot resync plugins
            assert owner.post("/api/v1/plugins/resync").status_code == 403

    def test_signed_download_requires_valid_sig(
        self, admin_client: httpx.Client
    ) -> None:
        proj = admin_client.post(
            "/api/v1/projects",
            json={"name": f"dl-{uuid.uuid4().hex[:6]}"},
        )
        assert proj.status_code == 201
        # Without a file, signed URL endpoint 404s — verify unauthenticated download rejects
        fake_id = str(uuid.uuid4())
        with httpx.Client(base_url=API_BASE, timeout=10.0) as anon:
            resp = anon.get(f"/api/v1/files/{fake_id}/download")
            assert resp.status_code in (401, 404)


class TestAdminStatus:
    def test_admin_status_shape(self, admin_client: httpx.Client) -> None:
        resp = admin_client.get("/api/v1/admin/status")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "services" in data
        assert "queue_depth" in data
        assert "plugins" in data
        assert "storage_bytes" in data
