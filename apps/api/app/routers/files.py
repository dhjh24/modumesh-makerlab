"""File metadata and controlled download routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import FileList, FileOut
from app.services import jobs as job_service
from app.services import projects as project_service
from app.services import storage

router = APIRouter(tags=["files"])


@router.get("/api/v1/projects/{project_id}/files", response_model=FileList)
async def list_project_files(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileList:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    items = await job_service.list_files_for_project(db, project_id)
    return FileList(items=[FileOut.model_validate(f) for f in items], total=len(items))


@router.get("/api/v1/files/{file_id}", response_model=FileOut)
async def get_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    file_obj = await job_service.get_file(db, file_id)
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileOut.model_validate(file_obj)


@router.get("/api/v1/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    file_obj = await job_service.get_file(db, file_id)
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data = storage.get_bytes(file_obj.object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch object: {exc}"
        ) from exc

    # Verify checksum integrity before serving
    digest = storage.sha256_bytes(data)
    if digest != file_obj.sha256:
        raise HTTPException(
            status_code=500,
            detail="Stored object checksum mismatch",
        )

    return Response(
        content=data,
        media_type=file_obj.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_obj.filename}"',
            "X-Checksum-SHA256": file_obj.sha256,
            "X-Object-Key": file_obj.object_key,
        },
    )


@router.get("/api/v1/jobs/{job_id}/files", response_model=FileList)
async def list_job_files(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileList:
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    items = await job_service.files_for_job(db, job_id)
    return FileList(items=[FileOut.model_validate(f) for f in items], total=len(items))
