"""Project API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import AuthContext, assert_project_access, require_auth
from app.schemas import (
    ProjectCreate,
    ProjectDeleteResult,
    ProjectList,
    ProjectOut,
    ProjectUpdate,
    VersionLockCreate,
    VersionLockOut,
)
from app.services import projects as project_service
from app.services import retention as retention_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.create_project(
        db,
        name=body.name,
        description=body.description,
        owner_id=auth.user.id,
        actor=auth.actor,
    )
    return ProjectOut.model_validate(project)


@router.get("", response_model=ProjectList)
async def list_projects(
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectList:
    owner_filter = None if auth.is_admin else auth.user.id
    items, total = await project_service.list_projects(
        db,
        owner_id=owner_filter,
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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    return ProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    try:
        project = await project_service.update_project(
            db,
            project,
            name=body.name,
            description=body.description,
            actor=auth.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    project = await project_service.archive_project(db, project, actor=auth.actor)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", response_model=ProjectDeleteResult)
async def delete_project(
    project_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProjectDeleteResult:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    result = await retention_service.delete_project(db, project, actor=auth.actor)
    return ProjectDeleteResult(**result)


@router.put("/{project_id}/version-locks", response_model=VersionLockOut)
async def upsert_version_lock(
    project_id: UUID,
    body: VersionLockCreate,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> VersionLockOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    lock = await project_service.set_version_lock(
        db,
        project,
        plugin_id=body.plugin_id,
        plugin_version=body.plugin_version,
        actor=auth.actor,
        notes=body.notes,
    )
    return VersionLockOut.model_validate(lock)


@router.get("/{project_id}/version-locks", response_model=list[VersionLockOut])
async def get_version_locks(
    project_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> list[VersionLockOut]:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    locks = await project_service.list_version_locks(db, project_id)
    return [VersionLockOut.model_validate(l) for l in locks]
