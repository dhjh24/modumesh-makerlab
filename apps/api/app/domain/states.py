"""Strict generation-job state machine.

Valid transitions:

    created ──► queued ──► running ──► validating ──► uploading ──► completed
       │           │           │            │             │
       └───────────┴───────────┴────────────┴─────────────┴──► cancelled
                                   │            │             │
                                   └────────────┴─────────────┴──► failed

Terminal states: completed, failed, cancelled.
Retry creates a *new* job linked via parent_job_id; it does not reopen a terminal job.
"""

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

ACTIVE_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.CREATED,
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.VALIDATING,
        JobStatus.UPLOADING,
    }
)

# States where a worker holds a lease / may be processing.
LEASED_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.RUNNING, JobStatus.VALIDATING, JobStatus.UPLOADING}
)

CANCELLABLE_STATUSES: frozenset[JobStatus] = frozenset(ACTIVE_STATUSES)

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
    """Raised when a job status transition is not allowed."""

    def __init__(self, current: JobStatus | str, target: JobStatus | str) -> None:
        self.current = JobStatus(current)
        self.target = JobStatus(target)
        super().__init__(
            f"Invalid job status transition: {self.current} → {self.target}"
        )


def validate_transition(current: JobStatus | str, target: JobStatus | str) -> None:
    """Raise InvalidTransitionError if current → target is not allowed."""
    cur = JobStatus(current)
    tgt = JobStatus(target)
    allowed = ALLOWED_TRANSITIONS.get(cur, frozenset())
    if tgt not in allowed:
        raise InvalidTransitionError(cur, tgt)


def can_transition(current: JobStatus | str, target: JobStatus | str) -> bool:
    try:
        validate_transition(current, target)
        return True
    except InvalidTransitionError:
        return False


def is_terminal(status: JobStatus | str) -> bool:
    return JobStatus(status) in TERMINAL_STATUSES


def is_cancellable(status: JobStatus | str) -> bool:
    return JobStatus(status) in CANCELLABLE_STATUSES
