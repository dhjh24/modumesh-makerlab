"""Job claim, transition, lease, and audit helpers for the worker."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import commit
from app.models import AuditEvent, GenerationJob
from app.states import JobStatus, validate_transition


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def record_audit(
    session: AsyncSession,
    *,
    entity_id: uuid.UUID,
    action: str,
    actor: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    session.add(
        AuditEvent(
            id=uuid.uuid4(),
            entity_type="generation_job",
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=details or {},
        )
    )


async def transition(
    session: AsyncSession,
    job: GenerationJob,
    target: JobStatus,
    *,
    worker_id: str,
    progress_pct: Optional[int] = None,
    progress_message: Optional[str] = None,
    error_message: Optional[str] = None,
) -> GenerationJob:
    validate_transition(job.status, target)
    previous = job.status
    job.status = target.value
    job.updated_at = _now()
    job.worker_id = worker_id
    if progress_pct is not None:
        job.progress_pct = progress_pct
    if progress_message is not None:
        job.progress_message = progress_message
    if error_message is not None:
        job.error_message = error_message

    if target == JobStatus.RUNNING:
        job.started_at = job.started_at or _now()
        job.heartbeat_at = _now()
        job.lease_expires_at = _now() + timedelta(seconds=settings.worker.lease_seconds)
    elif target in (JobStatus.VALIDATING, JobStatus.UPLOADING):
        job.heartbeat_at = _now()
        job.lease_expires_at = _now() + timedelta(seconds=settings.worker.lease_seconds)
    elif target in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        job.completed_at = _now()
        job.lease_expires_at = None
        if target == JobStatus.COMPLETED:
            job.progress_pct = 100

    await record_audit(
        session,
        entity_id=job.id,
        action=f"job.{target.value}",
        actor=worker_id,
        details={"from": previous, "to": target.value},
    )
    await session.flush()
    # Make status visible to the API / reaper immediately.
    await commit(session)
    return job


async def renew_lease(session: AsyncSession, job: GenerationJob, worker_id: str) -> None:
    job.heartbeat_at = _now()
    job.lease_expires_at = _now() + timedelta(seconds=settings.worker.lease_seconds)
    job.worker_id = worker_id
    job.updated_at = _now()
    await session.flush()
    await commit(session)


async def claim_job(
    session: AsyncSession,
    job_id: uuid.UUID,
    worker_id: str,
) -> Optional[GenerationJob]:
    """Atomically claim a queued job for processing."""
    result = await session.execute(
        select(GenerationJob)
        .where(GenerationJob.id == job_id)
        .with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    if job.cancel_requested or job.status == JobStatus.CANCELLED.value:
        if job.status == JobStatus.QUEUED.value:
            await transition(
                session,
                job,
                JobStatus.CANCELLED,
                worker_id=worker_id,
                progress_message="cancelled before claim",
            )
        return None

    if job.status != JobStatus.QUEUED.value:
        # Already claimed, cancelled, or finished — ignore.
        return None

    await transition(
        session,
        job,
        JobStatus.RUNNING,
        worker_id=worker_id,
        progress_pct=10,
        progress_message="claimed by worker",
    )
    return job


async def find_expired_leases(session: AsyncSession) -> list[GenerationJob]:
    result = await session.execute(
        select(GenerationJob).where(
            GenerationJob.status.in_(
                [
                    JobStatus.RUNNING.value,
                    JobStatus.VALIDATING.value,
                    JobStatus.UPLOADING.value,
                ]
            ),
            GenerationJob.lease_expires_at.is_not(None),
            GenerationJob.lease_expires_at < _now(),
        )
    )
    return list(result.scalars().all())
