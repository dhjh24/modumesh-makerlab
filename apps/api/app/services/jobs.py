"""Generation job service — create, transition, cancel, retry, progress."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.states import (
    InvalidTransitionError,
    JobStatus,
    is_cancellable,
    is_terminal,
    validate_transition,
)
from app.models import FileObject, GenerationJob, Project
from app.services.audit import record_audit
from app.services.queue import signal_cancel


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _find_by_idempotency(
    session: AsyncSession,
    project_id: uuid.UUID,
    key: str,
) -> Optional[GenerationJob]:
    return (
        await session.execute(
            select(GenerationJob).where(
                GenerationJob.project_id == project_id,
                GenerationJob.idempotency_key == key,
            )
        )
    ).scalar_one_or_none()


async def transition_job(
    session: AsyncSession,
    job: GenerationJob,
    target: JobStatus | str,
    *,
    actor: str = "system",
    progress_pct: Optional[int] = None,
    progress_message: Optional[str] = None,
    error_message: Optional[str] = None,
    worker_id: Optional[str] = None,
    extra_details: Optional[dict[str, Any]] = None,
) -> GenerationJob:
    """Apply a validated status transition and emit an audit event."""
    target_status = JobStatus(target)
    validate_transition(job.status, target_status)

    previous = job.status
    job.status = target_status.value
    job.updated_at = _now()

    if progress_pct is not None:
        job.progress_pct = progress_pct
    if progress_message is not None:
        job.progress_message = progress_message
    if error_message is not None:
        job.error_message = error_message
    if worker_id is not None:
        job.worker_id = worker_id

    if target_status == JobStatus.QUEUED:
        job.queued_at = _now()
    elif target_status == JobStatus.RUNNING:
        job.started_at = job.started_at or _now()
        job.heartbeat_at = _now()
    elif target_status in (
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    ):
        job.completed_at = _now()
        job.lease_expires_at = None
        if target_status == JobStatus.COMPLETED:
            job.progress_pct = 100
            job.progress_message = job.progress_message or "completed"

    await session.flush()

    details: dict[str, Any] = {
        "from": previous,
        "to": target_status.value,
    }
    if extra_details:
        details.update(extra_details)

    action_map = {
        JobStatus.QUEUED: "job.queued",
        JobStatus.RUNNING: "job.running",
        JobStatus.VALIDATING: "job.validating",
        JobStatus.UPLOADING: "job.uploading",
        JobStatus.COMPLETED: "job.completed",
        JobStatus.FAILED: "job.failed",
        JobStatus.CANCELLED: "job.cancelled",
    }
    await record_audit(
        session,
        entity_type="generation_job",
        entity_id=job.id,
        action=action_map.get(target_status, f"job.{target_status.value}"),
        actor=actor,
        details=details,
    )
    return job


async def create_job(
    session: AsyncSession,
    *,
    project: Project,
    job_type: str = "sample",
    input_payload: Optional[dict[str, Any]] = None,
    timeout_seconds: int = 60,
    idempotency_key: Optional[str] = None,
    actor: str = "api",
) -> tuple[GenerationJob, bool]:
    """Create a job and enqueue it.

    Returns (job, created). If an idempotency key matches an existing job,
    returns that job with created=False.
    """
    if project.status == "archived":
        raise ValueError("Cannot create jobs on an archived project")

    key = idempotency_key.strip() if idempotency_key else None
    if key == "":
        key = None

    if key is not None:
        existing = await _find_by_idempotency(session, project.id, key)
        if existing is not None:
            return existing, False

    job = GenerationJob(
        id=uuid.uuid4(),
        project_id=project.id,
        job_type=job_type,
        status=JobStatus.CREATED.value,
        input_payload=input_payload or {},
        timeout_seconds=timeout_seconds,
        idempotency_key=key,
        attempt_number=1,
        progress_pct=0,
        progress_message="created",
    )
    try:
        async with session.begin_nested():
            session.add(job)
            await session.flush()
    except IntegrityError:
        if key is not None:
            existing = await _find_by_idempotency(session, project.id, key)
            if existing is not None:
                return existing, False
        raise

    await record_audit(
        session,
        entity_type="generation_job",
        entity_id=job.id,
        action="job.created",
        actor=actor,
        details={"job_type": job_type, "idempotency_key": key},
    )

    await transition_job(
        session,
        job,
        JobStatus.QUEUED,
        actor=actor,
        progress_pct=5,
        progress_message="queued",
    )
    # Caller must enqueue after the DB transaction commits to avoid
    # workers claiming a job that is not yet durable.
    return job, True


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> Optional[GenerationJob]:
    return await session.get(GenerationJob, job_id)


async def list_jobs(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GenerationJob], int]:
    count_q = (
        select(func.count())
        .select_from(GenerationJob)
        .where(GenerationJob.project_id == project_id)
    )
    list_q = (
        select(GenerationJob)
        .where(GenerationJob.project_id == project_id)
        .order_by(GenerationJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    total = int((await session.execute(count_q)).scalar_one())
    items = list((await session.execute(list_q)).scalars().all())
    return items, total


async def cancel_job(
    session: AsyncSession,
    job: GenerationJob,
    *,
    actor: str = "api",
) -> GenerationJob:
    if not is_cancellable(job.status):
        raise InvalidTransitionError(job.status, JobStatus.CANCELLED)

    job.cancel_requested = True
    await session.flush()
    await signal_cancel(str(job.id))

    # Cooperative: if still created/queued, cancel immediately.
    # If running/validating/uploading, mark cancel_requested and let worker finish
    # the transition — but also allow forced cancel from API for queued/created.
    if job.status in (JobStatus.CREATED.value, JobStatus.QUEUED.value):
        return await transition_job(
            session,
            job,
            JobStatus.CANCELLED,
            actor=actor,
            progress_message="cancelled before start",
            extra_details={"mode": "immediate"},
        )

    await record_audit(
        session,
        entity_type="generation_job",
        entity_id=job.id,
        action="job.cancel_requested",
        actor=actor,
        details={"status": job.status},
    )
    return job


async def force_cancel_job(
    session: AsyncSession,
    job: GenerationJob,
    *,
    actor: str = "api",
) -> GenerationJob:
    """Force transition to cancelled (used when worker honors cancel)."""
    if is_terminal(job.status):
        if job.status == JobStatus.CANCELLED.value:
            return job
        raise InvalidTransitionError(job.status, JobStatus.CANCELLED)
    job.cancel_requested = True
    return await transition_job(
        session,
        job,
        JobStatus.CANCELLED,
        actor=actor,
        progress_message="cancelled",
        extra_details={"mode": "forced"},
    )


async def retry_job(
    session: AsyncSession,
    job: GenerationJob,
    *,
    actor: str = "api",
) -> GenerationJob:
    """Create a new attempt linked to the prior job."""
    if job.status not in (JobStatus.FAILED.value, JobStatus.CANCELLED.value):
        raise ValueError("Only failed or cancelled jobs can be retried")

    project = await session.get(Project, job.project_id)
    if project is None:
        raise ValueError("Project not found")
    if project.status == "archived":
        raise ValueError("Cannot retry jobs on an archived project")

    new_job = GenerationJob(
        id=uuid.uuid4(),
        project_id=job.project_id,
        parent_job_id=job.id,
        job_type=job.job_type,
        status=JobStatus.CREATED.value,
        input_payload=job.input_payload,
        timeout_seconds=job.timeout_seconds,
        idempotency_key=None,  # retries are new attempts; no idempotency reuse
        attempt_number=job.attempt_number + 1,
        progress_pct=0,
        progress_message="retry created",
    )
    session.add(new_job)
    await session.flush()

    await record_audit(
        session,
        entity_type="generation_job",
        entity_id=new_job.id,
        action="job.retry",
        actor=actor,
        details={
            "parent_job_id": str(job.id),
            "attempt_number": new_job.attempt_number,
        },
    )
    # Also audit on the parent
    await record_audit(
        session,
        entity_type="generation_job",
        entity_id=job.id,
        action="job.retried",
        actor=actor,
        details={"new_job_id": str(new_job.id)},
    )

    await transition_job(
        session,
        new_job,
        JobStatus.QUEUED,
        actor=actor,
        progress_pct=5,
        progress_message="queued",
    )
    # Caller must enqueue after commit.
    return new_job


async def update_progress(
    session: AsyncSession,
    job: GenerationJob,
    *,
    progress_pct: int,
    progress_message: Optional[str] = None,
) -> GenerationJob:
    job.progress_pct = max(0, min(100, progress_pct))
    if progress_message is not None:
        job.progress_message = progress_message
    job.updated_at = _now()
    job.heartbeat_at = _now()
    await session.flush()
    return job


async def list_files_for_project(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> list[FileObject]:
    result = await session.execute(
        select(FileObject)
        .where(FileObject.project_id == project_id)
        .order_by(FileObject.created_at.desc())
    )
    return list(result.scalars().all())


async def get_file(session: AsyncSession, file_id: uuid.UUID) -> Optional[FileObject]:
    return await session.get(FileObject, file_id)


async def files_for_job(
    session: AsyncSession,
    job_id: uuid.UUID,
) -> list[FileObject]:
    result = await session.execute(
        select(FileObject).where(FileObject.job_id == job_id)
    )
    return list(result.scalars().all())
