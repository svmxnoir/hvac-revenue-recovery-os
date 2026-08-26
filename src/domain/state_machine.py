"""State machine for revenue opportunity lifecycle.

Determines valid state transitions and enforces business rules.
"""

from .value_objects import OpportunityState, EventType


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid state transition."""

    pass


class StateTransitionRule:
    """Defines valid transitions from one state to another.
    
    FACT: Transitions are deterministic and exhaustive.
    ASSUMPTION: State machine is acyclic (no loops).
    DECISION: Terminal states have no valid outgoing transitions.
    """

    # Valid transitions: from_state -> set of valid to_states
    VALID_TRANSITIONS = {
        OpportunityState.DETECTED: {
            OpportunityState.ELIGIBILITY_PENDING,
            OpportunityState.CANCELLED,
        },
        OpportunityState.ELIGIBILITY_PENDING: {
            OpportunityState.ELIGIBLE,
            OpportunityState.BLOCKED,
            OpportunityState.CANCELLED,
        },
        OpportunityState.ELIGIBLE: {
            OpportunityState.CONTACTED,
            OpportunityState.BLOCKED,
            OpportunityState.CANCELLED,
        },
        OpportunityState.BLOCKED: {
            OpportunityState.LOST,
            OpportunityState.CANCELLED,
        },
        OpportunityState.CONTACTED: {
            OpportunityState.ENGAGED,
            OpportunityState.LOST,
            OpportunityState.CANCELLED,
        },
        OpportunityState.ENGAGED: {
            OpportunityState.QUALIFIED,
            OpportunityState.LOST,
            OpportunityState.CANCELLED,
        },
        OpportunityState.QUALIFIED: {
            OpportunityState.BOOKING_PENDING,
            OpportunityState.LOST,
            OpportunityState.CANCELLED,
        },
        OpportunityState.BOOKING_PENDING: {
            OpportunityState.BOOKED,
            OpportunityState.LOST,
            OpportunityState.CANCELLED,
        },
        OpportunityState.BOOKED: {
            OpportunityState.COMPLETED,
            OpportunityState.CANCELLED,
        },
        # Terminal states: no outgoing transitions
        OpportunityState.COMPLETED: set(),
        OpportunityState.LOST: set(),
        OpportunityState.CANCELLED: set(),
    }

    # Map events to expected state transitions
    EVENT_TRANSITIONS = {
        EventType.CALL_MISSED: (None, OpportunityState.DETECTED),
        EventType.RECOVERY_ELIGIBILITY_CHECKED: (
            OpportunityState.DETECTED,
            OpportunityState.ELIGIBILITY_PENDING,
        ),
        EventType.RECOVERY_INITIATED: (
            OpportunityState.ELIGIBLE,
            OpportunityState.CONTACTED,
        ),
        EventType.CUSTOMER_REPLIED: (
            OpportunityState.CONTACTED,
            OpportunityState.ENGAGED,
        ),
        EventType.LEAD_QUALIFIED: (
            OpportunityState.ENGAGED,
            OpportunityState.QUALIFIED,
        ),
        EventType.AVAILABILITY_CONFIRMED: (
            OpportunityState.QUALIFIED,
            OpportunityState.BOOKING_PENDING,
        ),
        EventType.BOOKING_CREATED: (
            OpportunityState.BOOKING_PENDING,
            OpportunityState.BOOKED,
        ),
        EventType.JOB_COMPLETED: (
            OpportunityState.BOOKED,
            OpportunityState.COMPLETED,
        ),
        EventType.RECOVERY_BLOCKED: (
            OpportunityState.ELIGIBILITY_PENDING,
            OpportunityState.BLOCKED,
        ),
        EventType.BOOKING_CANCELLED: (
            OpportunityState.BOOKED,
            OpportunityState.CANCELLED,
        ),
    }

    @staticmethod
    def can_transition(
        current_state: OpportunityState, target_state: OpportunityState
    ) -> bool:
        """Check if transition is valid.

        Args:
            current_state: Current opportunity state
            target_state: Proposed target state

        Returns:
            True if transition is allowed, False otherwise
        """
        if current_state not in StateTransitionRule.VALID_TRANSITIONS:
            return False
        return target_state in StateTransitionRule.VALID_TRANSITIONS[current_state]

    @staticmethod
    def validate_transition(
        current_state: OpportunityState, target_state: OpportunityState
    ) -> None:
        """Validate a state transition, raising if invalid.

        Args:
            current_state: Current opportunity state
            target_state: Proposed target state

        Raises:
            InvalidTransitionError: If transition is not allowed
        """
        if not StateTransitionRule.can_transition(current_state, target_state):
            raise InvalidTransitionError(
                f"Cannot transition from {current_state} to {target_state}"
            )

    @staticmethod
    def get_expected_transition(
        event_type: EventType,
    ) -> tuple[OpportunityState | None, OpportunityState] | None:
        """Get the expected state transition for an event type.

        Args:
            event_type: The event type

        Returns:
            Tuple of (from_state, to_state) or None if event doesn't drive transitions
        """
        return StateTransitionRule.EVENT_TRANSITIONS.get(event_type)
