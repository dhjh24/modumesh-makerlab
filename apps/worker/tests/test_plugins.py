"""Worker unit tests for plugin dispatch wiring."""

from __future__ import annotations

from app.config import settings
from app.states import JobStatus, validate_transition


def test_plugin_dir_default():
    assert settings.worker.plugin_dir


def test_state_machine_still_valid():
    validate_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    validate_transition(JobStatus.RUNNING, JobStatus.VALIDATING)
