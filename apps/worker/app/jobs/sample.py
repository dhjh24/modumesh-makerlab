"""Harmless sample job — generates a small JSON artifact (no CAD/plugins)."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.job_ops import renew_lease, transition
from app.models import FileObject, GenerationJob
from app.queue_keys import cancel_key
from app import redis as redis_mod
from app.states import JobStatus, InvalidTransitionError
from app.storage import put_bytes


class JobCancelled(Exception):
    """Cooperative cancellation."""


class JobTimedOut(Exception):
    """Forced timeout."""


async def _is_cancel_signaled(job_id: str) -> bool:
    if redis_mod.redis_client is None:
        return False
    return bool(await redis_mod.redis_client.get(cancel_key(job_id)))


async def _check_cancel_or_timeout(
    session: AsyncSession,
    job: GenerationJob,
    *,
    worker_id: str,
    started_monotonic: float,
) -> None:
    await session.refresh(job)
    if job.status in (
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    ):
        raise JobCancelled()
    if job.cancel_requested or await _is_cancel_signaled(str(job.id)):
        raise JobCancelled()

    elapsed = time.monotonic() - started_monotonic
    if elapsed > job.timeout_seconds:
        raise JobTimedOut(f"Job exceeded timeout of {job.timeout_seconds}s")

    await renew_lease(session, job, worker_id)


async def _step_delay() -> None:
    delay = max(0, settings.worker.sample_step_delay_ms) / 1000.0
    if delay:
        await asyncio.sleep(delay)


async def run_sample_job(
    session: AsyncSession,
    job: GenerationJob,
    *,
    worker_id: str,
) -> None:
    """Execute the Phase 2 sample job end-to-end."""
    started = time.monotonic()

    async def gate() -> None:
        await _check_cancel_or_timeout(
            session, job, worker_id=worker_id, started_monotonic=started
        )

    try:
        await gate()
        await _step_delay()

        # Optional test hook — allows integration tests to stretch runtime.
        force_sleep = float((job.input_payload or {}).get("force_sleep_seconds", 0) or 0)
        if force_sleep > 0:
            job.progress_message = f"sleeping {force_sleep}s (test hook)"
            await session.flush()
            end = time.monotonic() + force_sleep
            while time.monotonic() < end:
                await gate()
                await asyncio.sleep(min(0.2, end - time.monotonic()))

        # ── Generate harmless JSON artifact ──────────────────────────
        payload = {
            "job_id": str(job.id),
            "project_id": str(job.project_id),
            "job_type": job.job_type,
            "attempt": job.attempt_number,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": job.input_payload,
            "message": "ModuMesh MakerLab sample artifact (Phase 2)",
        }
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        filename = "sample-output.json"

        await gate()
        job.progress_pct = 40
        job.progress_message = "artifact generated"
        job.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await _step_delay()

        # ── validating ───────────────────────────────────────────────
        await transition(
            session,
            job,
            JobStatus.VALIDATING,
            worker_id=worker_id,
            progress_pct=60,
            progress_message="validating artifact",
        )
        await gate()
        if not data or len(data) < 2:
            raise ValueError("artifact validation failed: empty payload")
        await _step_delay()

        # ── uploading ────────────────────────────────────────────────
        await transition(
            session,
            job,
            JobStatus.UPLOADING,
            worker_id=worker_id,
            progress_pct=80,
            progress_message="uploading artifact",
        )
        await gate()

        stored = put_bytes(
            project_id=job.project_id,
            job_id=job.id,
            filename=filename,
            data=data,
            content_type="application/json",
        )

        file_row = FileObject(
            id=uuid.uuid4(),
            project_id=job.project_id,
            job_id=job.id,
            object_key=stored.object_key,
            filename=filename,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
        )
        session.add(file_row)
        await session.flush()
        await _step_delay()
        await gate()

        await transition(
            session,
            job,
            JobStatus.COMPLETED,
            worker_id=worker_id,
            progress_pct=100,
            progress_message="completed",
        )

    except JobCancelled:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.CANCELLED,
                    worker_id=worker_id,
                    progress_message="cancelled by request",
                )
            except InvalidTransitionError:
                pass

    except JobTimedOut as exc:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.FAILED,
                    worker_id=worker_id,
                    progress_message="timed out",
                    error_message=str(exc),
                )
            except InvalidTransitionError:
                pass

    except Exception as exc:
        await session.refresh(job)
        if job.status not in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ):
            try:
                await transition(
                    session,
                    job,
                    JobStatus.FAILED,
                    worker_id=worker_id,
                    progress_message="failed",
                    error_message=str(exc),
                )
            except InvalidTransitionError:
                pass
        else:
            raise
