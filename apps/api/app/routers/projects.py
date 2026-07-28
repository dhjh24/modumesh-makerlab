"""Project API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ProjectCreate,
    ProjectList,
    ProjectOut,
    ProjectUpdate,
)
from app.services import projects as project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.create_project(
        db, name=body.name, description=body.description
    )
    return ProjectOut.model_validate(project)


@router.get("", response_model=ProjectList)
async def list_projects(
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ProjectList:
    items, total = await project_service.list_projects(
        db, include_archived=include_archived, limit=limit, offset=offset
    )
    return ProjectList(
        items=[ProjectOut.model_validate(p) for p in items],
        total=total,
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        project = await project_service.update_project(
            db, project, name=body.name, description=body.description
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project = await project_service.archive_project(db, project)
    return ProjectOut.model_validate(project)
