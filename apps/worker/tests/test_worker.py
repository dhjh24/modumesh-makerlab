"""Worker unit tests for state machine and sample helpers."""

from __future__ import annotations

import pytest

from app.states import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    JobStatus,
    validate_transition,
)


def test_worker_config_imports() -> None:
    from app.config import Settings, WorkerSettings

    s = Settings()
    assert s.worker.poll_interval_seconds >= 1
    assert s.worker.lease_seconds >= 1


def test_worker_settings_defaults() -> None:
    from app.config import WorkerSettings

    ws = WorkerSettings()
    assert ws.concurrency >= 1
    assert ws.plugin_timeout_seconds >= 30
    assert ws.max_memory_mb >= 128
    assert ws.lease_seconds >= 5


def test_worker_redis_config() -> None:
    from app.config import RedisSettings

    rs = RedisSettings()
    assert "redis://" in rs.url


def test_happy_path_state_machine() -> None:
    path = [
        JobStatus.CREATED,
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.VALIDATING,
        JobStatus.UPLOADING,
        JobStatus.COMPLETED,
    ]
    for cur, nxt in zip(path, path[1:]):
        validate_transition(cur, nxt)


def test_invalid_transition_raises() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition(JobStatus.COMPLETED, JobStatus.RUNNING)


def test_terminal_have_no_exits() -> None:
    for status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        assert ALLOWED_TRANSITIONS[status] == frozenset()


def test_immutable_storage_key() -> None:
    from app.storage import build_immutable_key

    key = build_immutable_key(project_id="p", job_id="j", filename="a.json")
    assert "projects/p/jobs/j/" in key
    assert key.endswith("_a.json")
