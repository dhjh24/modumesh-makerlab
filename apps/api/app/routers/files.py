"""File metadata and controlled download routes (owner-scoped since GM-10)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas import FileList, FileOut
from app.security.auth import require_user
from app.services import jobs as job_service
from app.services import projects as project_service
from app.services import storage

router = APIRouter(tags=["files"])

# C0 control chars + DEL — includes CR/LF (header injection, audit L2) and
# the double quote that would break out of the quoted filename parameter.
_CONTROL_OR_QUOTE_RE = re.compile(r"[\x00-\x1f\x7f\"]")


def _safe_download_filename(filename: str, file_id: UUID) -> str:
    """Sanitize a user-controlled filename for a Content-Disposition header.

    Strips CR/LF and all other control characters (plus double quotes, which
    would terminate the quoted ``filename=`` parameter early). When nothing
    usable remains, falls back to a generated ``model-<id>.<ext>`` name —
    never an empty or header-breaking value.
    """
    cleaned = _CONTROL_OR_QUOTE_RE.sub("", filename or "").strip()
    # A bare extension (e.g. ".stl") or pure punctuation is not a usable
    # filename — fall back the same way as an empty result.
    if not cleaned or re.fullmatch(r"\.[A-Za-z0-9]{1,12}", cleaned):
        ext = ""
        match = re.search(r"\.([A-Za-z0-9]{1,12})$", filename or "")
        if match:
            ext = match.group(1)
        cleaned = f"model-{file_id}.{ext}" if ext else f"model-{file_id}"
    return cleaned


def _not_found(detail: str) -> HTTPException:
    # 404 (not 403) for unowned resources: never leak existence.
    return HTTPException(status_code=404, detail=detail)


def _not_found(detail: str) -> HTTPException:
    # 404 (not 403) for unowned resources: never leak existence.
    return HTTPException(status_code=404, detail=detail)


@router.get("/api/v1/projects/{project_id}/files", response_model=FileList)
async def list_project_files(
    project_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> FileList:
    project = await project_service.get_owned_project(
        db, project_id, current_user.id
    )
    if project is None:
        raise _not_found("Project not found")
    items = await job_service.list_files_for_project(db, project_id)
    return FileList(items=[FileOut.model_validate(f) for f in items], total=len(items))


@router.get("/api/v1/files/{file_id}", response_model=FileOut)
async def get_file(
    file_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    file_obj = await job_service.get_owned_file(db, file_id, current_user.id)
    if file_obj is None:
        raise _not_found("File not found")
    return FileOut.model_validate(file_obj)


@router.get("/api/v1/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # Ownership is verified before any object-storage access.
    file_obj = await job_service.get_owned_file(db, file_id, current_user.id)
    if file_obj is None:
        raise _not_found("File not found")
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
            "Content-Disposition": (
                'attachment; filename="'
                + _safe_download_filename(file_obj.filename, file_obj.id)
                + '"'
            ),
            "X-Checksum-SHA256": file_obj.sha256,
            "X-Object-Key": file_obj.object_key,
        },
    )


@router.get("/api/v1/jobs/{job_id}/files", response_model=FileList)
async def list_job_files(
    job_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> FileList:
    job = await job_service.get_owned_job(db, job_id, current_user.id)
    if job is None:
        raise _not_found("Job not found")
    items = await job_service.files_for_job(db, job_id)
    return FileList(items=[FileOut.model_validate(f) for f in items], total=len(items))
