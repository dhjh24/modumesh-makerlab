"""Ownership & trust-boundary tests (GM-10).

Users only ever see their own projects/jobs/files: other users' resources are
indistinguishable from missing ones (404, never 403), lists are filtered in
SQL, and anonymous requests get 401. Public routes (health, catalog, plugin
browse) stay open.
"""

from __future__ import annotations

import sqlite3
import uuid


def _register(client, prefix: str = "user") -> dict:
    email = f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "user_id": body["user"]["id"],
    }


def _seed_job(db_path, project_id, job_id=None) -> str:
    job_id = job_id or uuid.uuid4()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO generation_jobs (id, project_id, job_type, status, input_payload) "
            "VALUES (?, ?, 'sample', 'completed', '{}')",
            # SQLite stores UUIDs as 32-char hex without dashes (the ORM's
            # CHAR(32) emulation) — seed in the same format.
            (job_id.hex, uuid.UUID(str(project_id)).hex),
        )
        conn.commit()
    finally:
        conn.close()
    return str(job_id)


def _seed_file(db_path, project_id, file_id=None) -> str:
    file_id = file_id or uuid.uuid4()
    project_uuid = uuid.UUID(str(project_id))
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO files (id, project_id, object_key, filename, content_type, "
            "size_bytes, sha256) VALUES (?, ?, ?, 'a.stl', 'model/stl', 4, ?)",
            (
                file_id.hex,
                project_uuid.hex,
                f"projects/{project_uuid.hex}/jobs/x/a.stl",
                "ab" * 32,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return str(file_id)


class TestOwnerLifecycle:
    def test_owner_crud_lifecycle(self, seeded_client):
        alice = _register(seeded_client, prefix="alice")

        created = seeded_client.post(
            "/api/v1/projects",
            json={"name": "Alice's box", "description": "own project"},
            headers=alice["headers"],
        )
        assert created.status_code == 201
        project = created.json()
        assert project["owner_id"] == alice["user_id"]
        project_id = project["id"]

        listed = seeded_client.get("/api/v1/projects", headers=alice["headers"])
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["id"] == project_id

        got = seeded_client.get(
            f"/api/v1/projects/{project_id}", headers=alice["headers"]
        )
        assert got.status_code == 200
        assert got.json()["name"] == "Alice's box"

        updated = seeded_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Alice's box v2"},
            headers=alice["headers"],
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Alice's box v2"

        archived = seeded_client.post(
            f"/api/v1/projects/{project_id}/archive", headers=alice["headers"]
        )
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"

    def test_owner_can_access_own_job_and_file(self, seeded_client, db_path):
        alice = _register(seeded_client, prefix="alice")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "A"}, headers=alice["headers"]
        ).json()["id"]
        job_id = _seed_job(db_path, project_id)
        file_id = _seed_file(db_path, project_id)

        job = seeded_client.get(f"/api/v1/jobs/{job_id}", headers=alice["headers"])
        assert job.status_code == 200
        assert job.json()["project_id"] == project_id

        progress = seeded_client.get(
            f"/api/v1/jobs/{job_id}/progress", headers=alice["headers"]
        )
        assert progress.status_code == 200
        assert progress.json()["status"] == "completed"

        files = seeded_client.get(
            f"/api/v1/projects/{project_id}/files", headers=alice["headers"]
        )
        assert files.status_code == 200
        assert files.json()["total"] == 1

        meta = seeded_client.get(f"/api/v1/files/{file_id}", headers=alice["headers"])
        assert meta.status_code == 200
        assert meta.json()["filename"] == "a.stl"

        job_files = seeded_client.get(
            f"/api/v1/jobs/{job_id}/files", headers=alice["headers"]
        )
        assert job_files.status_code == 200


class TestCrossUserIsolation:
    def test_other_user_cannot_read_or_modify_project(self, seeded_client):
        alice = _register(seeded_client, prefix="alice")
        bob = _register(seeded_client, prefix="bob")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "Alice's"}, headers=alice["headers"]
        ).json()["id"]

        # All 404 — never 403, never the resource.
        got = seeded_client.get(f"/api/v1/projects/{project_id}", headers=bob["headers"])
        assert got.status_code == 404
        patched = seeded_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "stolen"},
            headers=bob["headers"],
        )
        assert patched.status_code == 404
        archived = seeded_client.post(
            f"/api/v1/projects/{project_id}/archive", headers=bob["headers"]
        )
        assert archived.status_code == 404

        # Bob's list is SQL-filtered: Alice's project never appears.
        listed = seeded_client.get("/api/v1/projects", headers=bob["headers"])
        assert listed.status_code == 200
        assert listed.json()["total"] == 0
        assert listed.json()["items"] == []

    def test_other_user_cannot_create_job_on_project(self, seeded_client):
        alice = _register(seeded_client, prefix="alice")
        bob = _register(seeded_client, prefix="bob")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "Alice's"}, headers=alice["headers"]
        ).json()["id"]

        job = seeded_client.post(
            f"/api/v1/projects/{project_id}/jobs",
            json={"job_type": "sample", "input_payload": {}},
            headers=bob["headers"],
        )
        assert job.status_code == 404

    def test_other_user_cannot_access_job(self, seeded_client, db_path):
        alice = _register(seeded_client, prefix="alice")
        bob = _register(seeded_client, prefix="bob")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "Alice's"}, headers=alice["headers"]
        ).json()["id"]
        job_id = _seed_job(db_path, project_id)

        # Exists, but Bob must see the same 404 as a missing job.
        got = seeded_client.get(f"/api/v1/jobs/{job_id}", headers=bob["headers"])
        assert got.status_code == 404
        progress = seeded_client.get(
            f"/api/v1/jobs/{job_id}/progress", headers=bob["headers"]
        )
        assert progress.status_code == 404
        cancel = seeded_client.post(
            f"/api/v1/jobs/{job_id}/cancel", headers=bob["headers"]
        )
        assert cancel.status_code == 404
        retry = seeded_client.post(
            f"/api/v1/jobs/{job_id}/retry", headers=bob["headers"]
        )
        assert retry.status_code == 404

    def test_other_user_cannot_access_files(self, seeded_client, db_path):
        alice = _register(seeded_client, prefix="alice")
        bob = _register(seeded_client, prefix="bob")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "Alice's"}, headers=alice["headers"]
        ).json()["id"]
        file_id = _seed_file(db_path, project_id)

        meta = seeded_client.get(f"/api/v1/files/{file_id}", headers=bob["headers"])
        assert meta.status_code == 404
        download = seeded_client.get(
            f"/api/v1/files/{file_id}/download", headers=bob["headers"]
        )
        assert download.status_code == 404
        listing = seeded_client.get(
            f"/api/v1/projects/{project_id}/files", headers=bob["headers"]
        )
        assert listing.status_code == 404

    def test_other_user_cannot_shop_handoff_or_pricing(self, seeded_client, db_path):
        alice = _register(seeded_client, prefix="alice")
        bob = _register(seeded_client, prefix="bob")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "Alice's"}, headers=alice["headers"]
        ).json()["id"]
        job_id = _seed_job(db_path, project_id)

        pricing = seeded_client.get(
            f"/api/v1/projects/{project_id}/jobs/{job_id}/pricing",
            headers=bob["headers"],
        )
        assert pricing.status_code == 404
        handoff = seeded_client.post(
            f"/api/v1/projects/{project_id}/jobs/{job_id}/shop-handoff",
            headers=bob["headers"],
        )
        assert handoff.status_code == 404
        order = seeded_client.post(
            "/api/v1/shop/submit-order",
            json={"project_id": project_id, "job_id": job_id},
            headers=bob["headers"],
        )
        assert order.status_code == 404

    def test_other_user_cannot_compare(self, seeded_client):
        alice = _register(seeded_client, prefix="alice")
        bob = _register(seeded_client, prefix="bob")
        project_id = seeded_client.post(
            "/api/v1/projects", json={"name": "Alice's"}, headers=alice["headers"]
        ).json()["id"]

        comparison = seeded_client.post(
            "/api/v1/compare",
            json={
                "project_id": project_id,
                "input_payload": {"width": 100},
                "generators": ["fixture-echo"],
            },
            headers=bob["headers"],
        )
        assert comparison.status_code == 404

        results = seeded_client.get(
            f"/api/v1/compare/{project_id}", headers=bob["headers"]
        )
        assert results.status_code == 404


class TestAnonymousAccess:
    def test_anonymous_gets_401_on_per_user_routes(self, seeded_client):
        some_id = str(uuid.uuid4())
        cases = [
            ("GET", "/api/v1/projects"),
            ("POST", "/api/v1/projects"),
            ("GET", f"/api/v1/projects/{some_id}"),
            ("GET", f"/api/v1/jobs/{some_id}"),
            ("GET", f"/api/v1/files/{some_id}/download"),
            ("POST", f"/api/v1/projects/{some_id}/jobs"),
        ]
        for method, url in cases:
            resp = seeded_client.request(method, url, json={} if method == "POST" else None)
            assert resp.status_code == 401, f"{method} {url} should be 401, got {resp.status_code}"
            assert resp.json()["detail"] == "Not authenticated"

    def test_public_routes_stay_public(self, seeded_client):
        # No token anywhere: health, catalog browse, plugin browse all open.
        assert seeded_client.get("/health").status_code == 200
        catalog = seeded_client.get("/api/v1/catalog")
        assert catalog.status_code == 200
        assert catalog.json()["items"] == []
        plugins = seeded_client.get("/api/v1/plugins")
        assert plugins.status_code == 200
        assert plugins.json()["items"] == []


class TestLegacyDefaultOwnerUnaffected:
    def test_ensure_default_owner_still_works(self, db_session):
        """The legacy local-owner path is preserved for pre-auth data."""
        import asyncio

        from app.services.projects import ensure_default_owner

        async def _run():
            async with db_session.factory() as session:
                user = await ensure_default_owner(session)
                await session.commit()
                return str(user.id)

        user_id = asyncio.run(_run())
        assert user_id == "00000000-0000-4000-8000-000000000001"

        # And it is idempotent.
        async def _again():
            async with db_session.factory() as session:
                user = await ensure_default_owner(session)
                return str(user.id)

        assert asyncio.run(_again()) == "00000000-0000-4000-8000-000000000001"
