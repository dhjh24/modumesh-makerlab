"""FastAPI application entry point with lifespan events."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import settings
from app.database import check_db_connectivity, close_db
from app.logging import configure_logging, get_logger
from app.minio import check_minio_connectivity, init_minio
from app.redis import check_redis_connectivity, close_redis, init_redis
from app.routers import files, health, jobs, projects


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    logger = get_logger("app")
    logger.info("starting up", service="modumesh-api", version=settings.api.version)

    # ── Initialize dependencies ──────────────────────────────────────
    # Redis (async)
    await init_redis()
    redis_status = await check_redis_connectivity()
    logger.info("redis connectivity", **redis_status)

    # MinIO (sync)
    try:
        init_minio()
        minio_status = check_minio_connectivity()
        logger.info("minio connectivity", **minio_status)
    except Exception as exc:
        logger.warning("minio initialization failed", error=str(exc))

    # Database (async) — lightweight ping
    db_status = await check_db_connectivity()
    logger.info("database connectivity", **db_status)

    yield  # ── Application runs here ─────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("shutting down")
    await close_redis()
    await close_db()
    logger.info("shutdown complete")


app = FastAPI(
    title="ModuMesh MakerLab API",
    version=settings.api.version,
    description="Self-hosted 3D generator platform API",
    lifespan=lifespan,
)

# ── Middleware: correlation ID ────────────────────────────────────────


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    from uuid import uuid4

    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


app.include_router(health.router)
app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(files.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "modumesh-api",
        "version": settings.api.version,
        "status": "running",
    }


# ── Configure logging on import ──────────────────────────────────────
configure_logging(
    log_level=settings.api.log_level,
    service="modumesh-api",
)
