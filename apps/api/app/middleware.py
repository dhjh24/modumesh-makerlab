"""Rate limiting and quota middleware for the MakerLab API."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter keyed by IP or owner_id.

    Limits: 60 requests/min per endpoint, 10 job submissions/min per user.
    """

    def __init__(self, app, *, default_rpm: int = 60, job_rpm: int = 10):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.job_rpm = job_rpm
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _rate_limit_key(self, request: Request) -> str:
        # Use X-Forwarded-For or client IP
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else "unknown"
        return ip

    def _check(self, key: str, rpm: int) -> None:
        now = time.time()
        window = 60.0
        timestamps = self._windows[key]
        # Prune timestamps outside the window
        cutoff = now - window
        self._windows[key] = [t for t in timestamps if t > cutoff]
        if len(self._windows[key]) >= rpm:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {rpm} requests per minute.",
                headers={"Retry-After": str(int(window))},
            )
        self._windows[key].append(now)

    async def dispatch(self, request: Request, call_next):
        key = self._rate_limit_key(request)

        # Stricter limit for job submission
        if request.method == "POST" and request.url.path.endswith("/jobs"):
            try:
                self._check(f"job:{key}", self.job_rpm)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        # Default limit for all other requests
        if request.method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            try:
                self._check(f"general:{key}", self.default_rpm)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        return await call_next(request)
