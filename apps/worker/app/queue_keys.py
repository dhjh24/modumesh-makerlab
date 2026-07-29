"""Redis queue key helpers (must match API)."""

from __future__ import annotations

JOB_QUEUE_KEY = "modumesh:jobs:queue"
JOB_CANCEL_PREFIX = "modumesh:jobs:cancel:"
JOB_LEASE_PREFIX = "modumesh:jobs:lease:"


def cancel_key(job_id: str) -> str:
    return f"{JOB_CANCEL_PREFIX}{job_id}"


def lease_key(job_id: str) -> str:
    return f"{JOB_LEASE_PREFIX}{job_id}"
