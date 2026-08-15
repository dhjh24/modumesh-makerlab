"""Prometheus metrics endpoint (GM-12 D4.1).

Serves ``GET /api/v1/metrics`` in Prometheus text format. Scrape-time gauges
(queue depth, active leases, terminal-job counts) are refreshed on each
request. The endpoint is internal-only: compose publishes no host port for it,
and an optional ``API_METRICS_TOKEN`` bearer token is enforced when set.

Follows the router style of ``app/routers/health.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST
from sqlalchemy import text

from app.config import settings
from app.database import async_session_factory
from app.logging import get_logger
from app.metrics import (
    ACTIVE_LEASES,
    JOB_TERMINAL,
    QUEUE_DEPTH,
    collect_registry,
)
from app.services.queue import queue_depth

router = APIRouter(tags=["metrics"])
log = get_logger("metrics")


async def _refresh_scrape_gauges() -> None:
    """Refresh gauges that reflect live system state.

    Every read is defensive: a scrape must never fail because a dependency
    hiccuped — unhealthy state shows up in the gauge values / health checks
    instead of a 500 on /metrics.
    """
    try:
        QUEUE_DEPTH.set(await queue_depth())
    except Exception as exc:  # noqa: BLE001
        QUEUE_DEPTH.set(0)
        log.warning("metrics: queue depth unavailable", error=str(exc))

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM generation_jobs "
                    "WHERE lease_expires_at IS NOT NULL "
                    "AND lease_expires_at > NOW()"
                )
            )
            ACTIVE_LEASES.set(int(result.scalar_one()))
    except Exception as exc:  # noqa: BLE001
        ACTIVE_LEASES.set(0)
        log.warning("metrics: active leases unavailable", error=str(exc))

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT status, job_type, COUNT(*) AS n "
                    "FROM generation_jobs "
                    "WHERE status IN ('completed', 'failed', 'cancelled') "
                    "GROUP BY status, job_type"
                )
            )
            for row in result.mappings():
                JOB_TERMINAL.labels(
                    status=row["status"], job_type=row["job_type"]
                ).set(int(row["n"]))
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics: terminal job counts unavailable", error=str(exc))


@router.get("/api/v1/metrics")
async def metrics_endpoint(request: Request, response: Response) -> Response:
    """Prometheus text exposition of API + worker metrics."""
    token = settings.api.metrics_token
    if token:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {token}":
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing metrics token",
            )

    await _refresh_scrape_gauges()
    body = collect_registry()
    response.headers["Content-Type"] = CONTENT_TYPE_LATEST
    response.headers["Cache-Control"] = "no-store"
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)
