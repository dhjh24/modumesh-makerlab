"""Rate limiting and quota middleware for the MakerLab API."""

from __future__ import annotations

import ipaddress
import time
from collections import OrderedDict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter keyed by IP or owner_id.

    Limits: 60 requests/min per endpoint, 10 job submissions/min per user.

    ``X-Forwarded-For`` is only trusted when the direct peer is a configured
    trusted proxy (``API_TRUSTED_PROXIES``, comma-separated CIDRs). With the
    default empty setting the header is never trusted, so clients cannot
    rotate it to bypass the caps. The tracked-key map is bounded (LRU-style
    eviction) so unique-IP flooding cannot grow memory without limit.
    """

    MAX_TRACKED_KEYS = 10_000

    def __init__(self, app, *, default_rpm: int = 60, job_rpm: int = 10):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.job_rpm = job_rpm
        self._windows: OrderedDict[str, list[float]] = OrderedDict()

    @staticmethod
    def _is_trusted_proxy(client_host: str | None) -> bool:
        """True when the direct peer is inside a configured trusted CIDR."""
        if not client_host:
            return False
        try:
            peer = ipaddress.ip_address(client_host)
        except ValueError:
            return False
        for entry in (settings.api.trusted_proxies or "").split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                network = ipaddress.ip_network(entry, strict=False)
            except ValueError:
                continue
            if peer in network:
                return True
        return False

    def _rate_limit_key(self, request: Request) -> str:
        # Only trust X-Forwarded-For from a configured trusted proxy;
        # otherwise an attacker just rotates the header to dodge the caps.
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded and self._is_trusted_proxy(
            request.client.host if request.client else None
        ):
            ip = forwarded.split(",")[0].strip()
            if ip:
                return ip
        return request.client.host if request.client else "unknown"

    def _check(self, key: str, rpm: int) -> None:
        now = time.time()
        window = 60.0
        cutoff = now - window

        # LRU bookkeeping: refresh recency so eviction drops the stalest keys.
        timestamps = self._windows.pop(key, [])
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= rpm:
            self._windows[key] = timestamps
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {rpm} requests per minute.",
                headers={"Retry-After": str(int(window))},
            )

        timestamps.append(now)
        self._windows[key] = timestamps
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Bound memory: drop keys with no activity in the window, then the
        least-recently-used keys until under the cap."""
        if len(self._windows) <= self.MAX_TRACKED_KEYS:
            return
        cutoff = time.time() - 60.0
        # Keys with no request inside the current window are dead weight.
        dead = [k for k, v in self._windows.items() if not any(t > cutoff for t in v)]
        for key in dead:
            del self._windows[key]
        # OrderedDict keeps insertion order; popitem(last=False) evicts the
        # least recently refreshed keys first (FIFO/LRU approximation).
        while len(self._windows) > self.MAX_TRACKED_KEYS:
            self._windows.popitem(last=False)

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
