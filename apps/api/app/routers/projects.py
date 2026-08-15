"""Project API routes (owner-scoped since GM-10)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import (
    ProjectCreate,
    ProjectList,
    ProjectOut,
    ProjectUpdate,
)
from app.security.auth import require_user
from app.services import projects as project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _not_found() -> HTTPException:
    # 404 (not 403) for unowned projects: never leak existence.
    return HTTPException(status_code=404, detail="Project not found")


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.create_project(
        db,
        name=body.name,
        description=body.description,
        owner_id=current_user.id,
        actor=str(current_user.id),
    )
    return ProjectOut.model_validate(project)


@router.get("", response_model=ProjectList)
async def list_projects(
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectList:
    # Filtered in SQL by owner — other users' projects are never returned.
    items, total = await project_service.list_projects(
        db,
        owner_id=current_user.id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return ProjectList(
        items=[ProjectOut.model_validate(p) for p in items],
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_owned_project(
        db, project_id, current_user.id
    )
    if project is None:
        raise _not_found()
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_owned_project(
        db, project_id, current_user.id
    )
    if project is None:
        raise _not_found()
    try:
        project = await project_service.update_project(
            db,
            project,
            name=body.name,
            description=body.description,
            actor=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_owned_project(
        db, project_id, current_user.id
    )
    if project is None:
        raise _not_found()
    project = await project_service.archive_project(
        db, project, actor=str(current_user.id)
    )
    return ProjectOut.model_validate(project)
