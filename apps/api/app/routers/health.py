"""Health check router — enriched with dependency connectivity status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.database import check_db_connectivity, async_session_factory
from app.minio import check_minio_connectivity, minio_write_test
from app.redis import check_redis_connectivity
from app.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger("health")


async def _worker_heartbeat_status() -> dict:
    """Check if any worker has recently heartbeated."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(*) AS active_workers, "
                    "MAX(heartbeat_at) AS latest_heartbeat "
                    "FROM generation_jobs "
                    "WHERE heartbeat_at IS NOT NULL "
                    "AND heartbeat_at > NOW() - INTERVAL '30 seconds'"
                )
            )
            row = result.one_or_none()
            if row and row.active_workers > 0:
                return {
                    "status": "ok",
                    "active_workers": row.active_workers,
                    "latest_heartbeat": (
                        row.latest_heartbeat.isoformat() if row.latest_heartbeat else None
                    ),
                }
            result = await session.execute(
                text(
                    "SELECT COUNT(*) AS leased_jobs, "
                    "MAX(lease_expires_at) AS latest_lease "
                    "FROM generation_jobs "
                    "WHERE lease_expires_at IS NOT NULL "
                    "AND lease_expires_at > NOW()"
                )
            )
            row = result.one_or_none()
            if row and row.leased_jobs > 0:
                return {"status": "ok", "active_workers": 1, "leased_jobs": row.leased_jobs}
            return {"status": "no_worker_seen", "active_workers": 0}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _plugin_discovery_status() -> dict:
    """Count plugins in the registry."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT "
                    "COUNT(*) AS total, "
                    "COUNT(*) FILTER (WHERE enabled IS TRUE AND status = 'active') AS enabled "
                    "FROM plugin_registry"
                )
            )
            row = result.one()
            return {
                "status": "ok",
                "total": row.total,
                "enabled": row.enabled,
            }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/health")
async def health_check() -> dict:
    """Overall health — lightweight checks of all dependencies."""
    db_status = await check_db_connectivity()
    redis_status = await check_redis_connectivity()
    minio_status = check_minio_connectivity()

    all_ok = all(
        s["status"] == "ok"
        for s in [db_status, redis_status, minio_status]
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "service": "modumesh-api",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_status,
            "redis": redis_status,
            "minio": minio_status,
        },
    }


@router.get("/health/ready")
async def readiness_check(response: Response) -> dict:
    """Readiness probe — all dependencies must be reachable."""
    db_status = await check_db_connectivity()
    redis_status = await check_redis_connectivity()
    minio_status = check_minio_connectivity()

    all_ready = all(
        s["status"] == "ok"
        for s in [db_status, redis_status, minio_status]
    )

    status_code = 200 if all_ready else 503
    response.status_code = status_code
    return {
        "status": "ready" if all_ready else "not_ready",
        "service": "modumesh-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_status,
            "redis": redis_status,
            "minio": minio_status,
        },
    }


@router.get("/health/live")
async def liveness_check() -> dict:
    """Liveness probe — confirms the process is alive (no deps checked)."""
    return {
        "status": "alive",
        "service": "modumesh-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/storage-test")
async def storage_test() -> dict:
    """End-to-end MinIO write/read test."""
    return await minio_write_test()


@router.get("/health/full")
async def full_health_check() -> dict:
    """Comprehensive health — all deps + worker + plugins."""
    db_status = await check_db_connectivity()
    redis_status = await check_redis_connectivity()
    minio_status = check_minio_connectivity()
    worker_status = await _worker_heartbeat_status()
    plugin_status = await _plugin_discovery_status()

    all_ok = all(
        s.get("status") == "ok"
        for s in [db_status, redis_status, minio_status, worker_status, plugin_status]
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "service": "modumesh-api",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_status,
            "redis": redis_status,
            "minio": minio_status,
            "worker": worker_status,
            "plugins": plugin_status,
        },
    }
