"""Health check router — enriched with dependency connectivity status."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response

from app.database import check_db_connectivity
from app.minio import check_minio_connectivity, minio_write_test
from app.redis import check_redis_connectivity

router = APIRouter(tags=["health"])


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
