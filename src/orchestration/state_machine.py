"""State machine for tracking research workflow state."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowState(Enum):
    """States of the research workflow."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    FETCHING_DATA = "fetching_data"
    LAYER1_EXECUTING = "layer1_executing"
    LAYER2_EXECUTING = "layer2_executing"
    LAYER3_EXECUTING = "layer3_executing"
    LAYER4_EXECUTING = "layer4_executing"
    CHECKING_CONVERGENCE = "checking_convergence"
    CONVERGED = "converged"
    GENERATING_REPORT = "generating_report"
    SENDING_NOTIFICATIONS = "sending_notifications"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StateTransition(BaseModel):
    """Record of a state transition."""

    from_state: WorkflowState
    to_state: WorkflowState
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowStateMachine:
    """State machine for managing research workflow."""

    # Define valid state transitions
    VALID_TRANSITIONS = {
        WorkflowState.IDLE: [WorkflowState.INITIALIZING, WorkflowState.CANCELLED],
        WorkflowState.INITIALIZING: [
            WorkflowState.FETCHING_DATA,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.FETCHING_DATA: [
            WorkflowState.LAYER1_EXECUTING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.LAYER1_EXECUTING: [
            WorkflowState.LAYER2_EXECUTING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.LAYER2_EXECUTING: [
            WorkflowState.LAYER3_EXECUTING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.LAYER3_EXECUTING: [
            WorkflowState.LAYER4_EXECUTING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.LAYER4_EXECUTING: [
            WorkflowState.CHECKING_CONVERGENCE,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.CHECKING_CONVERGENCE: [
            WorkflowState.CONVERGED,
            WorkflowState.FETCHING_DATA,  # Loop back for next iteration
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.CONVERGED: [
            WorkflowState.GENERATING_REPORT,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.GENERATING_REPORT: [
            WorkflowState.SENDING_NOTIFICATIONS,
            WorkflowState.COMPLETED,  # If no notifications configured
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.SENDING_NOTIFICATIONS: [
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        WorkflowState.COMPLETED: [],  # Terminal state
        WorkflowState.FAILED: [WorkflowState.IDLE],  # Can restart
        WorkflowState.CANCELLED: [WorkflowState.IDLE],  # Can restart
    }

    def __init__(self):
        """Initialize the state machine."""
        self._current_state = WorkflowState.IDLE
        self._transitions: list[StateTransition] = []
        self._context: dict[str, Any] = {}
        self._loop_number = 0

    @property
    def current_state(self) -> WorkflowState:
        """Get current state."""
        return self._current_state

    @property
    def loop_number(self) -> int:
        """Get current loop number."""
        return self._loop_number

    def can_transition(self, to_state: WorkflowState) -> bool:
        """Check if transition to state is valid.

        Args:
            to_state: Target state

        Returns:
            True if transition is valid
        """
        valid_targets = self.VALID_TRANSITIONS.get(self._current_state, [])
        return to_state in valid_targets

    def transition(
        self,
        to_state: WorkflowState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Transition to a new state.

        Args:
            to_state: Target state
            metadata: Optional metadata for the transition

        Returns:
            True if transition succeeded

        Raises:
            ValueError: If transition is invalid
        """
        if not self.can_transition(to_state):
            raise ValueError(
                f"Invalid transition from {self._current_state.value} to {to_state.value}"
            )

        transition = StateTransition(
            from_state=self._current_state,
            to_state=to_state,
            metadata=metadata or {},
        )
        self._transitions.append(transition)

        # Update loop counter
        if to_state == WorkflowState.LAYER1_EXECUTING:
            self._loop_number += 1

        self._current_state = to_state
        return True

    def reset(self) -> None:
        """Reset state machine to idle."""
        self._current_state = WorkflowState.IDLE
        self._transitions.clear()
        self._context.clear()
        self._loop_number = 0

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value.

        Args:
            key: Context key
            value: Context value
        """
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value.

        Args:
            key: Context key
            default: Default value if not found

        Returns:
            Context value
        """
        return self._context.get(key, default)

    def get_transitions(self) -> list[StateTransition]:
        """Get transition history.

        Returns:
            List of state transitions
        """
        return self._transitions.copy()

    def get_state_duration(self, state: WorkflowState) -> float:
        """Get total time spent in a state.

        Args:
            state: State to measure

        Returns:
            Total seconds spent in state
        """
        total = 0.0
        in_state = False
        entry_time = None

        for transition in self._transitions:
            if transition.to_state == state:
                in_state = True
                entry_time = transition.timestamp
            elif in_state and transition.from_state == state:
                if entry_time:
                    total += (transition.timestamp - entry_time).total_seconds()
                in_state = False
                entry_time = None

        # If still in state
        if in_state and entry_time:
            total += (datetime.utcnow() - entry_time).total_seconds()

        return total

    def is_terminal(self) -> bool:
        """Check if current state is terminal.

        Returns:
            True if in terminal state
        """
        return self._current_state in [
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ]

    def is_running(self) -> bool:
        """Check if workflow is currently running.

        Returns:
            True if running
        """
        return self._current_state not in [
            WorkflowState.IDLE,
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ]

    def get_status_summary(self) -> dict[str, Any]:
        """Get summary of current status.

        Returns:
            Status summary dict
        """
        return {
            "current_state": self._current_state.value,
            "loop_number": self._loop_number,
            "is_running": self.is_running(),
            "is_terminal": self.is_terminal(),
            "transition_count": len(self._transitions),
            "context_keys": list(self._context.keys()),
        }
