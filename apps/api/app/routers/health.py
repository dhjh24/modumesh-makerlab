"""Health check router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "modumesh-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness probe — confirms the API can serve traffic."""
    return {
        "status": "ready",
        "service": "modumesh-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/live")
async def liveness_check() -> dict:
    """Liveness probe — confirms the process is alive."""
    return {
        "status": "alive",
        "service": "modumesh-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
