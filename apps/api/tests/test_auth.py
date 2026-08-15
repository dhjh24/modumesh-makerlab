"""Auth API tests — register/login/logout/me + password & token primitives.

Runs against the real FastAPI app with an in-memory SQLite DB (see
conftest.py). Rate limiting is disabled session-wide; the rate-limit logic is
tested directly in test_rate_limiting.py.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from app.services import auth as auth_service


def _register(client, *, email=None, password="password123", display_name=None):
    payload = {"email": email or f"user-{uuid.uuid4().hex[:10]}@example.com", "password": password}
    if display_name is not None:
        payload["display_name"] = display_name
    return client.post("/api/v1/auth/register", json=payload)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRegister:
    def test_register_returns_token_and_user(self, seeded_client):
        resp = _register(seeded_client, email="alice@example.com", display_name="Alice")
        assert resp.status_code == 201
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert len(body["access_token"]) >= 32
        assert "expires_at" in body
        user = body["user"]
        assert user["email"] == "alice@example.com"
        assert user["display_name"] == "Alice"
        assert user["is_admin"] is False
        assert "created_at" in user

    def test_register_default_display_name_is_email_prefix(self, seeded_client):
        resp = _register(seeded_client, email="bob@example.com")
        assert resp.status_code == 201
        assert resp.json()["user"]["display_name"] == "bob"

    def test_register_email_is_case_insensitive_and_trimmed(self, seeded_client):
        resp = _register(seeded_client, email="  Carol@Example.COM ")
        assert resp.status_code == 201
        assert resp.json()["user"]["email"] == "carol@example.com"

    def test_register_duplicate_email_conflicts(self, seeded_client):
        first = _register(seeded_client, email="dup@example.com")
        assert first.status_code == 201
        second = _register(seeded_client, email="dup@example.com")
        assert second.status_code == 409
        assert second.json()["detail"] == "Email already registered"

    def test_register_weak_password_rejected(self, seeded_client):
        resp = _register(seeded_client, password="short")
        assert resp.status_code == 422

    def test_register_invalid_email_rejected(self, seeded_client):
        resp = _register(seeded_client, email="not-an-email")
        assert resp.status_code == 422

    def test_register_stores_only_token_hash_never_raw(self, seeded_client, db_path):
        resp = _register(seeded_client)
        assert resp.status_code == 201
        raw_token = resp.json()["access_token"]

        conn = sqlite3.connect(str(db_path))
        try:
            rows = conn.execute(
                "SELECT token_hash FROM auth_tokens"
            ).fetchall()
        finally:
            conn.close()

        assert len(rows) == 1
        stored_hash = rows[0][0]
        assert stored_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        assert len(stored_hash) == 64
        assert stored_hash != raw_token

    def test_register_password_is_hashed_never_plaintext(self, seeded_client, db_path):
        resp = _register(seeded_client, password="super-secret-99")
        assert resp.status_code == 201

        conn = sqlite3.connect(str(db_path))
        try:
            stored = conn.execute(
                "SELECT password_hash FROM users"
            ).fetchone()[0]
        finally:
            conn.close()

        assert stored.startswith("pbkdf2_sha256$")
        assert "super-secret-99" not in stored


class TestLogin:
    def test_login_success_returns_token(self, seeded_client):
        email = f"login-{uuid.uuid4().hex[:8]}@example.com"
        _register(seeded_client, email=email, password="password123")
        resp = seeded_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["user"]["email"] == email

    def test_login_wrong_password_rejected(self, seeded_client):
        email = f"login-{uuid.uuid4().hex[:8]}@example.com"
        _register(seeded_client, email=email, password="password123")
        resp = seeded_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_login_unknown_email_same_message_as_wrong_password(self, seeded_client):
        """No account enumeration: identical 401 for both failure modes."""
        wrong_pw = seeded_client.post(
            "/api/v1/auth/login",
            json={"email": f"exists-{uuid.uuid4().hex[:8]}@example.com", "password": "x" * 12},
        )
        unknown = seeded_client.post(
            "/api/v1/auth/login",
            json={"email": f"ghost-{uuid.uuid4().hex[:8]}@example.com", "password": "x" * 12},
        )
        assert wrong_pw.status_code == 401
        assert unknown.status_code == 401
        assert wrong_pw.json() == unknown.json()

    def test_login_email_case_insensitive(self, seeded_client):
        email = f"case-{uuid.uuid4().hex[:8]}@example.com"
        _register(seeded_client, email=email, password="password123")
        resp = seeded_client.post(
            "/api/v1/auth/login",
            json={"email": email.upper(), "password": "password123"},
        )
        assert resp.status_code == 200


class TestMe:
    def test_me_with_token(self, seeded_client):
        resp = _register(seeded_client, email="me@example.com")
        token = resp.json()["access_token"]
        me = seeded_client.get("/api/v1/auth/me", headers=_auth_headers(token))
        assert me.status_code == 200
        assert me.json()["email"] == "me@example.com"
        assert me.json()["id"] == resp.json()["user"]["id"]

    def test_me_without_token(self, seeded_client):
        resp = seeded_client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Not authenticated"

    def test_me_with_bad_token(self, seeded_client):
        resp = seeded_client.get("/api/v1/auth/me", headers=_auth_headers("not-a-real-token"))
        assert resp.status_code == 401

    def test_me_with_expired_token(self, seeded_client, monkeypatch):
        """A token whose expiry lies in the past must be rejected."""

        def _expired_token(user_id, ttl_hours=None):
            raw = f"expired-{uuid.uuid4().hex}"
            expires = datetime.now(timezone.utc) - timedelta(hours=1)
            return raw, expires

        monkeypatch.setattr(auth_service, "create_token", _expired_token)
        resp = _register(seeded_client, email="expired@example.com")
        assert resp.status_code == 201
        me = seeded_client.get(
            "/api/v1/auth/me", headers=_auth_headers(resp.json()["access_token"])
        )
        assert me.status_code == 401


class TestLogout:
    def test_logout_revokes_token(self, seeded_client):
        resp = _register(seeded_client)
        token = resp.json()["access_token"]
        headers = _auth_headers(token)

        assert seeded_client.get("/api/v1/auth/me", headers=headers).status_code == 200
        logout = seeded_client.post("/api/v1/auth/logout", headers=headers)
        assert logout.status_code == 204
        # The same token is now dead.
        assert seeded_client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_logout_requires_auth(self, seeded_client):
        resp = seeded_client.post("/api/v1/auth/logout")
        assert resp.status_code == 401


class TestPasswordPrimitives:
    def test_hash_password_format_and_roundtrip(self):
        stored = auth_service.hash_password("correct horse battery staple")
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        assert algo == "pbkdf2_sha256"
        assert int(iterations) == auth_service.PBKDF2_ITERATIONS
        assert len(salt_hex) == 32  # 16 random bytes
        assert len(hash_hex) == 64  # sha256
        assert auth_service.verify_password("correct horse battery staple", stored)
        assert not auth_service.verify_password("wrong password", stored)

    def test_hash_password_uses_per_user_salt(self):
        stored_a = auth_service.hash_password("same-password")
        stored_b = auth_service.hash_password("same-password")
        assert stored_a != stored_b

    def test_verify_password_rejects_garbage(self):
        assert not auth_service.verify_password("anything", "not-a-hash")
        assert not auth_service.verify_password("anything", "")
        assert not auth_service.verify_password("anything", "md5$1$00$00")

    def test_token_primitives(self):
        raw_a, expires_a = auth_service.create_token(uuid.uuid4(), ttl_hours=24)
        raw_b, _ = auth_service.create_token(uuid.uuid4(), ttl_hours=24)
        assert raw_a != raw_b
        assert len(raw_a) >= 32
        delta = expires_a - datetime.now(timezone.utc)
        assert timedelta(hours=23) < delta <= timedelta(hours=24)
        digest = auth_service.hash_token(raw_a)
        assert len(digest) == 64
        assert digest == hashlib.sha256(raw_a.encode()).hexdigest()
