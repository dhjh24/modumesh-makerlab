"""Rate-limit middleware unit tests (no app, no DB).

The middleware's in-memory windows are shared process-wide, so these tests
construct isolated ``RateLimitMiddleware`` instances and drive ``dispatch``
directly with hand-built ASGI scopes. Covers the GM-10 additions:
stricter caps on the credential endpoints and per-user keying for
authenticated requests (per-owner job quota).
"""

from __future__ import annotations

import uuid

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.middleware import AUTH_ENDPOINT_RPM, RateLimitMiddleware

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


def _request(path: str, *, method: str = "GET", token: str | None = None) -> Request:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("10.0.0.99", 5555),
        "server": ("testserver", 80),
    }
    return Request(scope)


async def _call_next(request: Request) -> Response:
    return Response(status_code=200)


def _middleware(*, default_rpm: int = 60, job_rpm: int = 10) -> RateLimitMiddleware:
    return RateLimitMiddleware(app=None, default_rpm=default_rpm, job_rpm=job_rpm)


class TestAuthEndpointCaps:
    @pytest.mark.asyncio
    async def test_register_capped_at_five_per_minute(self):
        mw = _middleware()
        for _ in range(5):
            resp = await mw.dispatch(
                _request("/api/v1/auth/register", method="POST"), _call_next
            )
            assert resp.status_code == 200
        resp = await mw.dispatch(
            _request("/api/v1/auth/register", method="POST"), _call_next
        )
        assert resp.status_code == 429
        assert isinstance(resp, JSONResponse)

    @pytest.mark.asyncio
    async def test_login_capped_separately_from_register(self):
        mw = _middleware()
        # 5 registers + 5 logins all pass (separate keys per prefix)…
        for _ in range(5):
            assert (await mw.dispatch(
                _request("/api/v1/auth/register", method="POST"), _call_next
            )).status_code == 200
            assert (await mw.dispatch(
                _request("/api/v1/auth/login", method="POST"), _call_next
            )).status_code == 200
        # …and the 6th of either is capped.
        assert (await mw.dispatch(
            _request("/api/v1/auth/login", method="POST"), _call_next
        )).status_code == 429
        assert (await mw.dispatch(
            _request("/api/v1/auth/register", method="POST"), _call_next
        )).status_code == 429

    @pytest.mark.asyncio
    async def test_other_endpoints_not_capped_by_auth_limit(self):
        mw = _middleware(default_rpm=60)
        # A different POST endpoint is only under the default 60/min cap.
        for _ in range(6):
            resp = await mw.dispatch(
                _request("/api/v1/projects", method="POST", token="tok-other"), _call_next
            )
            assert resp.status_code == 200


class TestPerUserKeying:
    @pytest.mark.asyncio
    async def test_job_cap_is_per_user_not_per_ip(self, monkeypatch):
        mw = _middleware(job_rpm=2)
        monkeypatch.setattr(
            "app.database.async_session_factory",
            _FakeFactory(USER_A),
        )
        # User A burns their own 2/min job budget from the shared IP.
        for _ in range(2):
            resp = await mw.dispatch(
                _request("/api/v1/projects/p/jobs", method="POST", token="token-a"),
                _call_next,
            )
            assert resp.status_code == 200
        assert (await mw.dispatch(
            _request("/api/v1/projects/p/jobs", method="POST", token="token-a"),
            _call_next,
        )).status_code == 429

        # User B (same IP, different token) has a fresh budget.
        monkeypatch.setattr("app.database.async_session_factory", _FakeFactory(USER_B))
        resp = await mw.dispatch(
            _request("/api/v1/projects/p/jobs", method="POST", token="token-b"),
            _call_next,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_job_cap_falls_back_to_ip_without_token(self, monkeypatch):
        mw = _middleware(job_rpm=2)
        # No token: keyed on IP even though a token factory is installed.
        monkeypatch.setattr("app.database.async_session_factory", _FakeFactory(USER_A))
        for _ in range(2):
            assert (await mw.dispatch(
                _request("/api/v1/projects/p/jobs", method="POST"), _call_next
            )).status_code == 200
        assert (await mw.dispatch(
            _request("/api/v1/projects/p/jobs", method="POST"), _call_next
        )).status_code == 429

    @pytest.mark.asyncio
    async def test_db_lookup_failure_falls_back_to_ip_key(self, monkeypatch):
        mw = _middleware(job_rpm=1)

        class _Boom:
            async def __aenter__(self):
                raise RuntimeError("db down")

            async def __aexit__(self, *a):
                return False

        monkeypatch.setattr(
            "app.database.async_session_factory",
            lambda: _Boom(),
        )
        # A token is present but the DB lookup explodes: quota still applies
        # on the IP key and the request itself is never broken.
        first = await mw.dispatch(
            _request("/api/v1/projects/p/jobs", method="POST", token="token-a"),
            _call_next,
        )
        assert first.status_code == 200
        second = await mw.dispatch(
            _request("/api/v1/projects/p/jobs", method="POST", token="token-a"),
            _call_next,
        )
        assert second.status_code == 429


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    def __init__(self, user_id):
        self._user_id = user_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, *args, **kwargs):
        return _FakeResult(self._user_id)


class _FakeFactory:
    def __init__(self, user_id):
        self._user_id = user_id

    def __call__(self):
        return _FakeSession(self._user_id)


def test_auth_endpoint_rpm_defaults():
    assert AUTH_ENDPOINT_RPM["/api/v1/auth/register"] == 5
    assert AUTH_ENDPOINT_RPM["/api/v1/auth/login"] == 5
