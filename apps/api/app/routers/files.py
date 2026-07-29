"""File metadata and signed temporary download routes."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import AuthContext, assert_project_access, get_optional_auth, require_auth
from app.schemas import FileList, FileOut, SignedDownloadOut
from app.security import sign_download, verify_download_signature
from app.services import jobs as job_service
from app.services import projects as project_service
from app.services import storage
from app.services.audit import record_audit

router = APIRouter(tags=["files"])


async def _require_file_access(
    db: AsyncSession,
    auth: AuthContext,
    file_id: UUID,
):
    file_obj = await job_service.get_file(db, file_id)
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")
    project = await project_service.get_project(db, file_obj.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    return file_obj, project


@router.get("/api/v1/projects/{project_id}/files", response_model=FileList)
async def list_project_files(
    project_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> FileList:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    items = await job_service.list_files_for_project(db, project_id)
    return FileList(items=[FileOut.model_validate(f) for f in items], total=len(items))


@router.get("/api/v1/files/{file_id}", response_model=FileOut)
async def get_file(
    file_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    file_obj, _ = await _require_file_access(db, auth, file_id)
    return FileOut.model_validate(file_obj)


@router.post("/api/v1/files/{file_id}/signed-url", response_model=SignedDownloadOut)
async def create_signed_download_url(
    file_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    ttl_seconds: int = Query(None, ge=30, le=3600),
) -> SignedDownloadOut:
    file_obj, _ = await _require_file_access(db, auth, file_id)
    ttl = ttl_seconds or settings.api.download_url_ttl_seconds
    expires_at = int(time.time()) + ttl
    signature = sign_download(
        secret=settings.api.download_signing_secret,
        file_id=file_obj.id,
        expires_at=expires_at,
        user_id=auth.user.id,
    )
    base = str(request.base_url).rstrip("/")
    url = (
        f"{base}/api/v1/files/{file_obj.id}/download"
        f"?expires={expires_at}&uid={auth.user.id}&sig={signature}"
    )
    await record_audit(
        db,
        entity_type="file",
        entity_id=file_obj.id,
        action="file.signed_url",
        actor=auth.actor,
        details={"expires_at": expires_at, "ttl_seconds": ttl},
    )
    return SignedDownloadOut(
        file_id=file_obj.id,
        url=url,
        expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc),
        expires_in_seconds=ttl,
    )


@router.get("/api/v1/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext | None = Depends(get_optional_auth),
    expires: int | None = Query(None),
    uid: UUID | None = Query(None),
    sig: str | None = Query(None),
    redirect: bool = Query(False),
) -> Response:
    file_obj = await job_service.get_file(db, file_id)
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")

    actor = "anonymous"
    allowed = False

    if expires is not None and uid is not None and sig:
        allowed = verify_download_signature(
            secret=settings.api.download_signing_secret,
            file_id=file_id,
            expires_at=expires,
            user_id=uid,
            signature=sig,
        )
        actor = str(uid)
    elif auth is not None:
        project = await project_service.get_project(db, file_obj.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        assert_project_access(auth, project)
        allowed = True
        actor = auth.actor

    if not allowed:
        raise HTTPException(status_code=401, detail="Authentication or signed URL required")

    await record_audit(
        db,
        entity_type="file",
        entity_id=file_obj.id,
        action="file.downloaded",
        actor=actor,
        details={"filename": file_obj.filename, "via": "signed" if sig else "session"},
    )

    if redirect:
        try:
            url = storage.presigned_get_url(
                file_obj.object_key,
                expires_seconds=settings.api.download_url_ttl_seconds,
            )
            return RedirectResponse(url=url, status_code=307)
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Failed to create presigned URL: {exc}"
            ) from exc

    try:
        data = storage.get_bytes(file_obj.object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to fetch object: {exc}"
        ) from exc

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
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> FileList:
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    project = await project_service.get_project(db, job.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    items = await job_service.files_for_job(db, job_id)
    return FileList(items=[FileOut.model_validate(f) for f in items], total=len(items))
