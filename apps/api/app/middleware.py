"""HTTP middleware: security headers, rate limits, request size, correlation logs."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.logging import get_logger
from app.metrics import metrics

logger = get_logger("http")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        # Avoid breaking interactive OpenAPI UIs under /docs and /redoc.
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
        if settings.api.session_cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        max_bytes = settings.api.max_request_bytes
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body exceeds {max_bytes} bytes"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length"},
                )
        return await call_next(request)


class _SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


_rate_limiter = _SlidingWindow()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client = request.client.host if request.client else "unknown"
        path = request.url.path
        if path.startswith("/health") or path == "/metrics":
            return await call_next(request)

        limit = settings.api.rate_limit_per_minute
        bucket = "api"
        if path.startswith("/api/v1/auth/login"):
            limit = settings.api.rate_limit_auth_per_minute
            bucket = "auth-login"
        elif path.startswith("/api/"):
            bucket = "api"
        else:
            bucket = path.split("/")[1] if path.startswith("/") and len(path) > 1 else "root"

        key = f"{client}:{bucket}"
        if not _rate_limiter.allow(key, limit):
            metrics.inc("http_rate_limited_total")
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


class CorrelationLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        request.state.correlation_id = correlation_id
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = response.status_code if response is not None else 500
            if response is not None:
                response.headers["X-Correlation-ID"] = correlation_id
            metrics.inc("http_requests_total", labels={"status": str(status_code)})
            metrics.observe("http_request_duration_ms", elapsed_ms)
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=elapsed_ms,
                correlation_id=correlation_id,
                client=request.client.host if request.client else None,
            )
