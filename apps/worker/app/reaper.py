"""Lease reaper — fails abandoned jobs with expired leases."""

from __future__ import annotations

from app.database import session_scope
from app.job_ops import find_expired_leases, transition
from app.logging import get_logger
from app.states import JobStatus, InvalidTransitionError

log = get_logger("reaper")


async def reap_expired_leases(worker_id: str) -> int:
    """Mark abandoned leased jobs as failed. Returns count reaped."""
    reaped = 0
    async with session_scope() as session:
        expired = await find_expired_leases(session)
        for job in expired:
            try:
                await transition(
                    session,
                    job,
                    JobStatus.FAILED,
                    worker_id=worker_id,
                    progress_message="lease expired",
                    error_message=(
                        f"Worker lease expired (last worker={job.worker_id}); "
                        "job marked failed for retry"
                    ),
                )
                reaped += 1
                log.warning(
                    "reaped abandoned job",
                    job_id=str(job.id),
                    previous_worker=job.worker_id,
                )
            except InvalidTransitionError:
                continue
    return reaped
