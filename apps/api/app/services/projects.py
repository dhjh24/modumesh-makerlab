"""Project CRUD service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.services.audit import record_audit

DEFAULT_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


async def ensure_default_owner(session: AsyncSession) -> User:
    user = await session.get(User, DEFAULT_OWNER_ID)
    if user is not None:
        return user
    user = User(
        id=DEFAULT_OWNER_ID,
        external_id="local-default",
        display_name="Local Owner",
    )
    session.add(user)
    await session.flush()
    return user


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
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Project], int]:
    filters = []
    if not include_archived:
        filters.append(Project.status == "active")

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
