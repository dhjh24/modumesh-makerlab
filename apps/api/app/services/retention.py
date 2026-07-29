"""Data retention and project hard-delete with object cleanup."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import FileObject, Project
from app.services.audit import record_audit
from app.services import storage


async def delete_project(
    session: AsyncSession,
    project: Project,
    *,
    actor: str = "api",
) -> dict[str, Any]:
    """Hard-delete a project, its jobs/files rows (CASCADE), and MinIO objects."""
    files = list(
        (
            await session.execute(
                select(FileObject).where(FileObject.project_id == project.id)
            )
        ).scalars().all()
    )
    deleted_objects = 0
    failed_objects: list[str] = []
    for f in files:
        try:
            if storage.delete_object(f.object_key):
                deleted_objects += 1
        except Exception:  # noqa: BLE001
            failed_objects.append(f.object_key)

    project_id = project.id
    await record_audit(
        session,
        entity_type="project",
        entity_id=project_id,
        action="project.deleted",
        actor=actor,
        details={
            "name": project.name,
            "files_removed": deleted_objects,
            "object_failures": failed_objects,
        },
    )
    await session.delete(project)
    await session.flush()
    return {
        "project_id": str(project_id),
        "files_removed": deleted_objects,
        "object_failures": failed_objects,
    }


async def purge_expired(
    session: AsyncSession,
    *,
    actor: str = "system",
    retention_days: int | None = None,
) -> dict[str, Any]:
    """Purge archived projects older than retention_days."""
    days = settings.api.retention_days if retention_days is None else retention_days
    if days <= 0:
        return {
            "purged_projects": 0,
            "retention_days": days,
            "skipped": True,
            "reason": "retention disabled",
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(Project).where(
            Project.status == "archived",
            Project.archived_at.is_not(None),
            Project.archived_at < cutoff,
        )
    )
    projects = list(result.scalars().all())
    purged = 0
    details: list[dict[str, Any]] = []
    for project in projects:
        info = await delete_project(session, project, actor=actor)
        purged += 1
        details.append(info)

    await record_audit(
        session,
        entity_type="system",
        entity_id=uuid.UUID("00000000-0000-4000-8000-000000000099"),
        action="retention.purge",
        actor=actor,
        details={"purged_projects": purged, "retention_days": days},
    )
    return {
        "purged_projects": purged,
        "retention_days": days,
        "skipped": False,
        "projects": details,
    }
