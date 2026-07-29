"""Phase 6 unit tests — tokens, passwords, middleware helpers."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.middleware import RateLimitMiddleware, RequestSizeLimitMiddleware, _SlidingWindow
from app.security.passwords import hash_password, verify_password
from app.security.tokens import (
    generate_session_token,
    hash_token,
    sign_download,
    verify_download_signature,
)


class TestPasswords:
    def test_hash_and_verify(self) -> None:
        h = hash_password("secret-password")
        assert h != "secret-password"
        assert verify_password("secret-password", h)
        assert not verify_password("wrong", h)


class TestTokens:
    def test_session_token_hash(self) -> None:
        t = generate_session_token()
        assert len(t) > 20
        assert hash_token(t) != t
        assert hash_token(t) == hash_token(t)

    def test_download_signature_roundtrip(self) -> None:
        secret = "test-secret"
        file_id = uuid4()
        user_id = uuid4()
        expires = int(time.time()) + 60
        sig = sign_download(
            secret=secret, file_id=file_id, expires_at=expires, user_id=user_id
        )
        assert verify_download_signature(
            secret=secret,
            file_id=file_id,
            expires_at=expires,
            user_id=user_id,
            signature=sig,
        )
        assert not verify_download_signature(
            secret=secret,
            file_id=file_id,
            expires_at=expires,
            user_id=user_id,
            signature="deadbeef",
        )

    def test_download_signature_expired(self) -> None:
        secret = "test-secret"
        file_id = uuid4()
        user_id = uuid4()
        expires = int(time.time()) - 10
        sig = sign_download(
            secret=secret, file_id=file_id, expires_at=expires, user_id=user_id
        )
        assert not verify_download_signature(
            secret=secret,
            file_id=file_id,
            expires_at=expires,
            user_id=user_id,
            signature=sig,
        )


class TestSlidingWindow:
    def test_allows_under_limit_then_blocks(self) -> None:
        window = _SlidingWindow()
        assert window.allow("k", limit=2, window_seconds=60.0)
        assert window.allow("k", limit=2, window_seconds=60.0)
        assert not window.allow("k", limit=2, window_seconds=60.0)


@pytest.mark.asyncio
async def test_request_size_limit_rejects_large_content_length() -> None:
    async def call_next(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    middleware = RequestSizeLimitMiddleware(app=None)  # type: ignore[arg-type]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/projects",
        "raw_path": b"/api/v1/projects",
        "query_string": b"",
        "headers": [(b"content-length", b"999999999")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    request = Request(scope)
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import middleware as mw
    from app.config import settings

    monkeypatch.setattr(settings.api, "rate_limit_per_minute", 1)
    limiter = _SlidingWindow()
    monkeypatch.setattr(mw, "_rate_limiter", limiter)

    async def call_next(_request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    middleware = RateLimitMiddleware(app=None)  # type: ignore[arg-type]

    def make_request() -> Request:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/projects",
            "raw_path": b"/api/v1/projects",
            "query_string": b"",
            "headers": [],
            "client": ("10.0.0.9", 12345),
            "server": ("test", 80),
        }
        return Request(scope)

    first = await middleware.dispatch(make_request(), call_next)
    second = await middleware.dispatch(make_request(), call_next)
    assert first.status_code == 200
    assert second.status_code == 429
