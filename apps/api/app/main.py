"""FastAPI application entry point with lifespan events."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import check_db_connectivity, close_db
from app.logging import configure_logging, get_logger
from app.metrics import metrics
from app.middleware import (
    CorrelationLoggingMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.minio import check_minio_connectivity, init_minio
from app.redis import check_redis_connectivity, close_redis, init_redis
from app.routers import admin, auth, files, health, jobs, plugins, projects


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    logger = get_logger("app")
    logger.info("starting up", service="modumesh-api", version=settings.api.version)

    await init_redis()
    redis_status = await check_redis_connectivity()
    logger.info("redis connectivity", **redis_status)

    try:
        init_minio()
        minio_status = check_minio_connectivity()
        logger.info("minio connectivity", **minio_status)
    except Exception as exc:
        logger.warning("minio initialization failed", error=str(exc))

    db_status = await check_db_connectivity()
    logger.info("database connectivity", **db_status)

    try:
        from app.database import async_session_factory
        from app.services import auth as auth_service
        from app.services import plugins as plugin_service

        async with async_session_factory() as session:
            await auth_service.ensure_bootstrap_users(session)
            summary = await plugin_service.sync_registry(session, actor="startup")
            await session.commit()
            logger.info(
                "bootstrap ready",
                discovered=summary.get("discovered"),
                issues=len(summary.get("issues") or []),
                auth_enabled=settings.api.auth_enabled,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup bootstrap skipped", error=str(exc))

    yield

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

# Middleware order: last added runs first on request.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CorrelationLoggingMiddleware)

_cors_origins = [
    origin.strip()
    for origin in (settings.api.cors_origins or "").split(",")
    if origin.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-ID",
            "X-API-Token",
            "Accept",
        ],
        expose_headers=["X-Correlation-ID", "X-Checksum-SHA256", "X-Object-Key"],
    )

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(files.router)
app.include_router(plugins.router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "modumesh-api",
        "version": settings.api.version,
        "status": "running",
    }


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    if not settings.api.metrics_enabled:
        return Response(status_code=404, content="metrics disabled")
    return Response(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


configure_logging(
    log_level=settings.api.log_level,
    service="modumesh-api",
)
