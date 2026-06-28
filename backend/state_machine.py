"""
Case finite state machine.
Enforces valid transitions and raises on illegal ones.
"""

VALID_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["COMPILED"],
    "COMPILED": ["EXECUTING"],
    "EXECUTING": ["PAUSED", "AWAITING_HUMAN", "CLOSED_SUCCESS", "FAILED"],
    "PAUSED": ["AWAITING_HUMAN", "RESUMING", "CLOSED_FAILURE", "EXECUTING"],
    "AWAITING_HUMAN": ["RESUMING", "CLOSED_FAILURE", "SUSPENDED"],
    "RESUMING": ["EXECUTING"],
    "FAILED": ["AWAITING_HUMAN", "CLOSED_FAILURE"],
    "SUSPENDED": ["DRAFT", "CLOSED_FAILURE"],
    "CLOSED_SUCCESS": [],
    "CLOSED_FAILURE": [],
}

TERMINAL_STATES = {"CLOSED_SUCCESS", "CLOSED_FAILURE", "SUSPENDED"}


class InvalidTransitionError(Exception):
    pass


def validate_transition(current_status: str, new_status: str) -> None:
    """Raise InvalidTransitionError if transition is not allowed."""
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Invalid transition: {current_status} → {new_status}. "
            f"Allowed from {current_status}: {allowed}"
        )


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATES
