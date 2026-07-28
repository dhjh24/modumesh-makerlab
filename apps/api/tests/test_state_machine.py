"""Unit tests for the job state machine."""

from __future__ import annotations

import pytest

from app.domain.states import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    JobStatus,
    can_transition,
    is_cancellable,
    is_terminal,
    validate_transition,
)


class TestStateMachine:
    def test_happy_path_transitions(self) -> None:
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

    def test_cancel_from_each_active_state(self) -> None:
        for status in (
            JobStatus.CREATED,
            JobStatus.QUEUED,
            JobStatus.RUNNING,
            JobStatus.VALIDATING,
            JobStatus.UPLOADING,
        ):
            assert can_transition(status, JobStatus.CANCELLED)
            assert is_cancellable(status)

    def test_fail_from_processing_states(self) -> None:
        for status in (JobStatus.RUNNING, JobStatus.VALIDATING, JobStatus.UPLOADING):
            assert can_transition(status, JobStatus.FAILED)

    def test_terminal_states_reject_all(self) -> None:
        for status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            assert is_terminal(status)
            assert ALLOWED_TRANSITIONS[status] == frozenset()
            for target in JobStatus:
                assert not can_transition(status, target)

    def test_invalid_skip_rejected(self) -> None:
        with pytest.raises(InvalidTransitionError):
            validate_transition(JobStatus.CREATED, JobStatus.RUNNING)
        with pytest.raises(InvalidTransitionError):
            validate_transition(JobStatus.QUEUED, JobStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            validate_transition(JobStatus.RUNNING, JobStatus.QUEUED)

    def test_cannot_fail_from_queued(self) -> None:
        assert not can_transition(JobStatus.QUEUED, JobStatus.FAILED)

    def test_storage_key_immutable_format(self) -> None:
        from app.services.storage import build_immutable_key, sha256_bytes

        key = build_immutable_key(
            project_id="proj",
            job_id="job",
            filename="out.json",
        )
        assert key.startswith("projects/proj/jobs/job/")
        assert key.endswith("_out.json")
        assert sha256_bytes(b"abc") == (
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )
