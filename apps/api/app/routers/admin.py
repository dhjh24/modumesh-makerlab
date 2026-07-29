"""Administrator status and retention endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import check_db_connectivity, get_db
from app.deps import AuthContext, require_admin
from app.minio import check_minio_connectivity
from app.models import FileObject, GenerationJob, PluginRegistryEntry, Project
from app.redis import check_redis_connectivity
from app.schemas import AdminStatusOut, RetentionPurgeResult
from app.services import retention as retention_service
from app.services.queue import queue_depth

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/status", response_model=AdminStatusOut)
async def admin_status(
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminStatusOut:
    db_status = await check_db_connectivity()
    redis_status = await check_redis_connectivity()
    minio_status = check_minio_connectivity()

    depth = await queue_depth()
    failed = int(
        (
            await db.execute(
                select(func.count())
                .select_from(GenerationJob)
                .where(GenerationJob.status == "failed")
            )
        ).scalar_one()
    )
    active_jobs = int(
        (
            await db.execute(
                select(func.count())
                .select_from(GenerationJob)
                .where(
                    GenerationJob.status.in_(
                        ["queued", "running", "validating", "uploading"]
                    )
                )
            )
        ).scalar_one()
    )
    projects = int(
        (await db.execute(select(func.count()).select_from(Project))).scalar_one()
    )
    storage_bytes = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(FileObject.size_bytes), 0))
            )
        ).scalar_one()
    )
    file_count = int(
        (await db.execute(select(func.count()).select_from(FileObject))).scalar_one()
    )

    plugins = list(
        (
            await db.execute(
                select(PluginRegistryEntry).order_by(PluginRegistryEntry.plugin_id)
            )
        )
        .scalars()
        .all()
    )
    plugin_health = [
        {
            "plugin_id": p.plugin_id,
            "version": p.version,
            "enabled": p.enabled,
            "status": p.status,
            "diagnostics": p.diagnostics,
        }
        for p in plugins
    ]

    return AdminStatusOut(
        timestamp=datetime.now(timezone.utc),
        services={
            "database": db_status,
            "redis": redis_status,
            "minio": minio_status,
        },
        queue_depth=depth,
        active_jobs=active_jobs,
        failed_jobs=failed,
        project_count=projects,
        storage_bytes=storage_bytes,
        file_count=file_count,
        plugins=plugin_health,
        retention_days=settings.api.retention_days,
        version=settings.api.version,
    )


@router.post("/retention/purge", response_model=RetentionPurgeResult)
async def purge_retention(
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> RetentionPurgeResult:
    result = await retention_service.purge_expired(db, actor=auth.actor)
    return RetentionPurgeResult(**result)


@router.get("/audit")
async def list_audit(
    limit: int = 100,
    offset: int = 0,
    auth: AuthContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    limit = min(max(limit, 1), 500)
    rows = (
        await db.execute(
            text(
                "SELECT id, entity_type, entity_id, action, actor, details, created_at "
                "FROM audit_events ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"limit": limit, "offset": offset},
        )
    ).mappings().all()
    return {
        "items": [
            {
                "id": str(r["id"]),
                "entity_type": r["entity_type"],
                "entity_id": str(r["entity_id"]),
                "action": r["action"],
                "actor": r["actor"],
                "details": r["details"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }
