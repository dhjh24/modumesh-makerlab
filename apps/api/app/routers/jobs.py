"""Generation job API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import AuthContext, assert_project_access, require_auth
from app.domain.states import InvalidTransitionError
from app.schemas import JobCreate, JobList, JobOut, JobProgress
from app.services import jobs as job_service
from app.services import plugins as plugin_service
from app.services import projects as project_service
from app.services.queue import enqueue_job

router = APIRouter(tags=["jobs"])


async def _job_with_access(
    db: AsyncSession, auth: AuthContext, job_id: UUID
):
    job = await job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    project = await project_service.get_project(db, job.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    return job, project


@router.post(
    "/api/v1/projects/{project_id}/jobs",
    response_model=JobOut,
)
async def create_job(
    project_id: UUID,
    body: JobCreate,
    response: Response,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobOut:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)

    plugin_version = body.plugin_version
    timeout_seconds = body.timeout_seconds

    if body.job_type == "sample":
        if body.plugin_version is not None:
            raise HTTPException(
                status_code=400,
                detail="plugin_version is not applicable to job_type 'sample'",
            )
    else:
        entry = await plugin_service.get_plugin(
            db,
            body.job_type,
            body.plugin_version,
            enabled_only=True,
        )
        if entry is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown or disabled plugin '{body.job_type}'"
                    + (f"@{body.plugin_version}" if body.plugin_version else "")
                ),
            )
        plugin_version = entry.version
        timeout_seconds = min(body.timeout_seconds, entry.timeout_seconds)

        try:
            from modumesh_plugin_sdk.validation import validate_input_payload

            validate_input_payload(
                entry.input_schema,
                body.input_payload,
                max_bytes=entry.max_input_bytes,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Honor project version lock when present.
        locks = await project_service.list_version_locks(db, project_id)
        for lock in locks:
            if lock.plugin_id == body.job_type and lock.plugin_version != plugin_version:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Project is locked to {lock.plugin_id}@{lock.plugin_version}"
                    ),
                )

    try:
        job, created = await job_service.create_job(
            db,
            project=project,
            job_type=body.job_type,
            input_payload=body.input_payload,
            timeout_seconds=timeout_seconds,
            idempotency_key=idempotency_key,
            plugin_version=plugin_version,
            actor=auth.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if created:
        await db.commit()
        await enqueue_job(str(job.id))

    response.status_code = 201 if created else 200
    if not created:
        response.headers["Idempotent-Replayed"] = "true"
    return JobOut.model_validate(job)


@router.get("/api/v1/projects/{project_id}/jobs", response_model=JobList)
async def list_project_jobs(
    project_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> JobList:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_project_access(auth, project)
    items, total = await job_service.list_jobs(
        db, project_id=project_id, limit=limit, offset=offset
    )
    return JobList(items=[JobOut.model_validate(j) for j in items], total=total)


@router.get("/api/v1/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    job, _ = await _job_with_access(db, auth, job_id)
    return JobOut.model_validate(job)


@router.get("/api/v1/jobs/{job_id}/progress", response_model=JobProgress)
async def get_job_progress(
    job_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> JobProgress:
    job, _ = await _job_with_access(db, auth, job_id)
    return JobProgress(
        id=job.id,
        status=job.status,
        progress_pct=job.progress_pct,
        progress_message=job.progress_message,
        error_message=job.error_message,
        cancel_requested=job.cancel_requested,
        updated_at=job.updated_at,
    )


@router.post("/api/v1/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    job, _ = await _job_with_access(db, auth, job_id)
    try:
        job = await job_service.cancel_job(db, job, actor=auth.actor)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JobOut.model_validate(job)


@router.post("/api/v1/jobs/{job_id}/retry", response_model=JobOut, status_code=201)
async def retry_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    job, _ = await _job_with_access(db, auth, job_id)
    try:
        new_job = await job_service.retry_job(db, job, actor=auth.actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await enqueue_job(str(new_job.id))
    return JobOut.model_validate(new_job)
