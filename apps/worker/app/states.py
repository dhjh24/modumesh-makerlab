"""Strict generation-job state machine (mirrors API domain)."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)

LEASED_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.RUNNING, JobStatus.VALIDATING, JobStatus.UPLOADING}
)

ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.CREATED: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset(
        {JobStatus.VALIDATING, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.VALIDATING: frozenset(
        {JobStatus.UPLOADING, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.UPLOADING: frozenset(
        {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


class InvalidTransitionError(ValueError):
    def __init__(self, current: JobStatus | str, target: JobStatus | str) -> None:
        self.current = JobStatus(current)
        self.target = JobStatus(target)
        super().__init__(
            f"Invalid job status transition: {self.current} → {self.target}"
        )


def validate_transition(current: JobStatus | str, target: JobStatus | str) -> None:
    cur = JobStatus(current)
    tgt = JobStatus(target)
    if tgt not in ALLOWED_TRANSITIONS.get(cur, frozenset()):
        raise InvalidTransitionError(cur, tgt)
