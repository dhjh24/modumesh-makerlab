"""FastAPI application entry point with lifespan events."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validate_boot_secrets
from app.database import check_db_connectivity, close_db
from app.logging import configure_logging, get_logger
from app.metrics import HTTP_REQUESTS
from app.middleware import RateLimitMiddleware
from app.minio import check_minio_connectivity, init_minio
from app.redis import check_redis_connectivity, close_redis, init_redis
from app.routers import (
    admin,
    auth,
    catalog,
    compare,
    files,
    health,
    jobs,
    metrics,
    plugins,
    projects,
    shop,
    shop_connector,
    submissions,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    logger = get_logger("app")
    logger.info("starting up", service="modumesh-api", version=settings.api.version)

    # ── Fail-closed security configuration validation ────────────────
    # Refuse to boot when admin auth is unconfigured or the default
    # signing secret is in use — otherwise admin endpoints would be
    # reachable without a key (or signed with a publicly known secret).
    # GM-9 made this unconditional (no API_ENV escape hatch).
    if not settings.admin.admin_api_key:
        raise RuntimeError(
            "Refusing to start: ADMIN_API_KEY is not set. Admin endpoints "
            "(plugin signing, quota, plugin control) are fail-closed and "
            "unusable without it. Set ADMIN_API_KEY (and a unique "
            "ADMIN_PLUGIN_SIGNING_SECRET) in the environment."
        )
    if settings.admin.plugin_signing_secret == "dev-secret":
        raise RuntimeError(
            "Refusing to start: ADMIN_PLUGIN_SIGNING_SECRET is still the "
            "default 'dev-secret'. Set a unique, non-default secret."
        )

    # GM-12 D1.2: datastore secrets fail-closed when API_ENV != development.
    # (Deliberately separate from the admin check above — admin stays
    # unconditional, datastore validation is gated on the deployment env.)
    validate_boot_secrets(
        api_env=settings.api.api_env,
        postgres_password=settings.postgres.password,
        minio_secret_key=settings.minio.secret_key,
        redis_password=settings.redis.password,
    )

    # ── Alembic migrations: explicit deploy step (GM-12 D1.6) ─────────
    # Off by default: run `alembic upgrade head` as an explicit deploy step
    # so replicas don't race and drift stays visible. Opt in with
    # API_RUN_MIGRATIONS=1 for single-instance deployments.
    if settings.api.run_migrations:
        try:
            import subprocess

            result = subprocess.run(
                ["alembic", "-c", os.path.join(os.path.dirname(__file__), "..", "alembic.ini"), "upgrade", "head"],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "PYTHONPATH": os.path.join(os.path.dirname(__file__), "..")},
            )
            if result.returncode == 0:
                logger.info("alembic migrations applied", output=result.stdout.strip())
            else:
                logger.warning("alembic migration failed", stderr=result.stderr.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("alembic migration skipped (non-fatal)", error=str(exc))
    else:
        logger.info(
            "alembic migrations skipped",
            reason="API_RUN_MIGRATIONS is not set to 1; run `alembic upgrade head` as an explicit deploy step",
        )

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

    # Plugin registry discovery (best-effort; migrations may not be applied yet)
    try:
        from app.database import async_session_factory
        from app.services import plugins as plugin_service

        async with async_session_factory() as session:
            summary = await plugin_service.sync_registry(session, actor="startup")
            await session.commit()
            logger.info(
                "plugin registry ready",
                discovered=summary.get("discovered"),
                issues=len(summary.get("issues") or []),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("plugin registry sync skipped", error=str(exc))

    yield  # ── Application runs here ─────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("shutting down")
    await close_redis()
    await close_db()
    logger.info("shutdown complete")


def create_app(api_env: str | None = None) -> FastAPI:
    """Build the FastAPI application.

    ``api_env`` overrides ``settings.api.api_env`` (used by unit tests).
    When the resolved environment is anything other than "development",
    interactive docs and the OpenAPI schema are disabled (GM-12 D1.4).
    """
    env = api_env if api_env is not None else settings.api.api_env
    docs_enabled = env == "development"

    app = FastAPI(
        title="ModuMesh MakerLab API",
        version=settings.api.version,
        description="Self-hosted 3D generator platform API",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
    )

    # ── Middleware: CORS (browser clients on the web origin) ─────────
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
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Correlation-ID", "X-Request-ID", "X-Checksum-SHA256", "X-Object-Key"],
        )

    # ── Middleware: correlation ID + request ID + request metrics ────
    # Each request gets a fresh uuid4 request_id (X-Request-ID header, bound
    # into structlog context) plus the existing correlation_id (echoed from
    # the client when present, for error-response correlation). The same
    # pass increments the HTTP request counter for /api/v1/metrics.

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        from uuid import uuid4

        structlog.contextvars.clear_contextvars()
        request_id = str(uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
        )
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id

        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or request.url.path
        HTTP_REQUESTS.labels(
            method=request.method,
            route=route_path,
            status=response.status_code,
        ).inc()
        return response

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(jobs.router)
    app.include_router(shop.router)
    app.include_router(submissions.router)
    app.include_router(compare.router)
    app.include_router(shop_connector.router)
    app.include_router(admin.router)
    app.include_router(catalog.router)
    app.include_router(files.router)
    app.include_router(plugins.router)
    if settings.api.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            default_rpm=settings.api.rate_limit_rpm,
            job_rpm=settings.api.job_rate_limit_rpm,
        )

    @app.get("/")
    async def root() -> dict:
        return {
            "service": "modumesh-api",
            "version": settings.api.version,
            "status": "running",
        }

    return app


app = create_app()

# ── Configure logging on import ──────────────────────────────────────
configure_logging(
    log_level=settings.api.log_level,
    service="modumesh-api",
)
