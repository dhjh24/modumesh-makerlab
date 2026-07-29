"""Domain logic for projects and the generation job engine."""

from app.domain.states import (
    ALLOWED_TRANSITIONS,
    ACTIVE_STATUSES,
    CANCELLABLE_STATUSES,
    InvalidTransitionError,
    JobStatus,
    LEASED_STATUSES,
    TERMINAL_STATUSES,
    can_transition,
    is_cancellable,
    is_terminal,
    validate_transition,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "ACTIVE_STATUSES",
    "CANCELLABLE_STATUSES",
    "InvalidTransitionError",
    "JobStatus",
    "LEASED_STATUSES",
    "TERMINAL_STATUSES",
    "can_transition",
    "is_cancellable",
    "is_terminal",
    "validate_transition",
]
