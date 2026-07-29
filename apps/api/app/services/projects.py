"""Project CRUD service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User, VersionLock
from app.services import auth as auth_service
from app.services.audit import record_audit

DEFAULT_OWNER_ID = auth_service.DEFAULT_OWNER_ID


async def ensure_default_owner(session: AsyncSession) -> User:
    return await auth_service.ensure_bootstrap_users(session)


async def create_project(
    session: AsyncSession,
    *,
    name: str,
    description: Optional[str] = None,
    owner_id: Optional[uuid.UUID] = None,
    actor: str = "api",
) -> Project:
    await ensure_default_owner(session)
    project = Project(
        id=uuid.uuid4(),
        owner_id=owner_id or DEFAULT_OWNER_ID,
        name=name,
        description=description,
        status="active",
    )
    session.add(project)
    await session.flush()
    await record_audit(
        session,
        entity_type="project",
        entity_id=project.id,
        action="project.created",
        actor=actor,
        details={"name": name},
    )
    return project


async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Optional[Project]:
    return await session.get(Project, project_id)


async def list_projects(
    session: AsyncSession,
    *,
    owner_id: Optional[uuid.UUID] = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Project], int]:
    filters = []
    if not include_archived:
        filters.append(Project.status == "active")
    if owner_id is not None:
        filters.append(Project.owner_id == owner_id)

    count_q = select(func.count()).select_from(Project)
    list_q = select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
    for f in filters:
        count_q = count_q.where(f)
        list_q = list_q.where(f)

    total = int((await session.execute(count_q)).scalar_one())
    items = list((await session.execute(list_q)).scalars().all())
    return items, total


async def update_project(
    session: AsyncSession,
    project: Project,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    actor: str = "api",
) -> Project:
    if project.status == "archived":
        raise ValueError("Cannot update an archived project")
    changes: dict = {}
    if name is not None:
        project.name = name
        changes["name"] = name
    if description is not None:
        project.description = description
        changes["description"] = description
    project.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await record_audit(
        session,
        entity_type="project",
        entity_id=project.id,
        action="project.updated",
        actor=actor,
        details=changes,
    )
    return project


async def archive_project(
    session: AsyncSession,
    project: Project,
    *,
    actor: str = "api",
) -> Project:
    if project.status == "archived":
        return project
    project.status = "archived"
    project.archived_at = datetime.now(timezone.utc)
    project.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await record_audit(
        session,
        entity_type="project",
        entity_id=project.id,
        action="project.archived",
        actor=actor,
        details={},
    )
    return project


async def set_version_lock(
    session: AsyncSession,
    project: Project,
    *,
    plugin_id: str,
    plugin_version: str,
    actor: str,
    notes: Optional[str] = None,
) -> VersionLock:
    result = await session.execute(
        select(VersionLock).where(
            VersionLock.project_id == project.id,
            VersionLock.plugin_id == plugin_id,
        )
    )
    lock = result.scalar_one_or_none()
    if lock is None:
        lock = VersionLock(
            id=uuid.uuid4(),
            project_id=project.id,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            locked_by=actor,
            notes=notes,
        )
        session.add(lock)
        action = "version_lock.created"
    else:
        lock.plugin_version = plugin_version
        lock.locked_by = actor
        lock.locked_at = datetime.now(timezone.utc)
        lock.notes = notes
        action = "version_lock.updated"
    await session.flush()
    await record_audit(
        session,
        entity_type="project",
        entity_id=project.id,
        action=action,
        actor=actor,
        details={
            "plugin_id": plugin_id,
            "plugin_version": plugin_version,
        },
    )
    return lock


async def list_version_locks(
    session: AsyncSession, project_id: uuid.UUID
) -> list[VersionLock]:
    result = await session.execute(
        select(VersionLock).where(VersionLock.project_id == project_id)
    )
    return list(result.scalars().all())
