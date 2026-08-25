"""Core domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from types import MappingProxyType
from .value_objects import (
    TenantId,
    CustomerId,
    OpportunityId,
    EventId,
    InterventionId,
    BookingId,
    JobId,
    RevenueRecordId,
    AttributionId,
    ConversationId,
    EventType,
    OpportunityState,
    ConsentStatus,
    MessagePurpose,
    AttributionType,
    AttributionStatus,
    RejectionReason,
    JobStatus,
    BookingOrigin,
    MessageSender,
    Money,
    _make_immutable,
)


@dataclass
class Tenant:
    """Represents an HVAC contractor tenant.
    
    FACT: Each tenant is isolated.
    ASSUMPTION: Tenant has a name and contact info.
    DECISION: Use dataclass for simplicity.
    """

    tenant_id: TenantId
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Customer:
    """Represents a customer of the tenant.
    
    FACT: Customer is tied to a specific tenant.
    ASSUMPTION: Phone number is required for inbound call tracking.
    DECISION: Store minimal identifying info; external systems provide details.
    """

    customer_id: CustomerId
    tenant_id: TenantId
    phone: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Message:
    """Immutable message in a conversation.
    
    FACT: Messages are immutable records of communication.
    DECISION: Separate from AI interpretation for auditability.
    """

    message_id: str
    sender: MessageSender
    content: str
    occurred_at: datetime
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate message and make metadata immutable."""
        if not self.content.strip():
            raise ValueError("Message content cannot be empty")
        # Make metadata immutable if provided
        if self.metadata is not None:
            object.__setattr__(
                self, "metadata", MappingProxyType(self.metadata)
            )


@dataclass(frozen=True)
class Event:
    """Immutable event record in the append-only ledger.
    
    FACT: Events are truly immutable, including payload.
    ASSUMPTION: source_event_id enables idempotency.
    DECISION: payload is frozen at construction; no mutations allowed.
    """

    event_id: EventId
    tenant_id: TenantId
    event_type: EventType
    occurred_at: datetime
    recorded_at: datetime
    source: str  # e.g., "TWILIO", "JOBBER", "SYSTEM"
    source_event_id: str  # External event ID for idempotency
    entity_type: str  # e.g., "OPPORTUNITY", "CUSTOMER", "BOOKING"
    entity_id: str  # ID of the entity affected
    payload: MappingProxyType[str, Any]  # Immutable payload
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        """Ensure payload is truly immutable."""
        # If payload somehow wasn't frozen at construction, freeze it now
        if not isinstance(self.payload, MappingProxyType):
            object.__setattr__(
                self,
                "payload",
                MappingProxyType(self.payload),
            )

    @staticmethod
    def create(
        event_id: EventId,
        tenant_id: TenantId,
        event_type: EventType,
        occurred_at: datetime,
        recorded_at: datetime,
        source: str,
        source_event_id: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        schema_version: str = "1.0",
    ) -> "Event":
        """Factory to create an Event with frozen payload.
        
        Args:
            event_id: Event ID
            tenant_id: Tenant ID
            event_type: Type of event
            occurred_at: When event occurred
            recorded_at: When event was recorded
            source: Source system
            source_event_id: External event ID
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            payload: Event payload (will be frozen)
            schema_version: Schema version
            
        Returns:
            Event with frozen payload
        """
        frozen_payload = MappingProxyType(
            {k: _make_immutable(v) for k, v in payload.items()}
        )
        return Event(
            event_id=event_id,
            tenant_id=tenant_id,
            event_type=event_type,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            source=source,
            source_event_id=source_event_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=frozen_payload,
            schema_version=schema_version,
        )


@dataclass
class ConsentState:
    """Tracks customer consent status for recovery interventions.
    
    FACT: Consent can be UNKNOWN, ELIGIBLE, SUPPRESSED, or OPTED_OUT.
    ASSUMPTION: Opt-out is permanent until explicitly revoked.
    DECISION: Track source and timestamp of every state change.
    """

    customer_id: CustomerId
    tenant_id: TenantId
    consent_status: ConsentStatus
    consent_source: Optional[str]  # e.g., "INITIAL_CHECK", "EXPLICIT_GRANT"
    consent_timestamp: Optional[datetime]
    opt_out_timestamp: Optional[datetime]
    suppression_reason: Optional[str]
    updated_at: datetime


@dataclass
class Intervention:
    """Represents a recovery intervention attempt.
    
    FACT: Intervention is initiated after eligibility is confirmed.
    ASSUMPTION: Purpose is SERVICE_RECOVERY (marketing excluded from M0).
    DECISION: Track message content and delivery status.
    """

    intervention_id: InterventionId
    opportunity_id: OpportunityId
    tenant_id: TenantId
    customer_id: CustomerId
    message_purpose: MessagePurpose
    message_content: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    created_at: datetime


@dataclass
class Conversation:
    """Represents customer response(s) to intervention.
    
    FACT: Conversation captures customer intent after intervention.
    ASSUMPTION: Can contain multiple messages from customer.
    DECISION: Store AI interpretation separately for auditability.
    """

    conversation_id: ConversationId
    intervention_id: InterventionId
    tenant_id: TenantId
    customer_id: CustomerId
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation.
        
        Args:
            message: Message to add
        """
        self.messages.append(message)
        self.updated_at = datetime.utcnow()


class RevenueOpportunityError(Exception):
    """Raised when an invalid opportunity state transition is attempted."""

    pass


@dataclass
class RevenueOpportunity:
    """Core entity representing a potential revenue recovery.
    
    FACT: Lifecycle spans from detected to completed or lost.
    ASSUMPTION: State transitions are deterministic and controlled.
    DECISION: State transitions via explicit methods, not direct mutation.
    """

    opportunity_id: OpportunityId
    tenant_id: TenantId
    customer_id: CustomerId
    state: OpportunityState
    missed_call_at: datetime
    detected_at: datetime
    eligible_reason: Optional[str] = None
    blocked_reason: Optional[str] = None
    intervention_id: Optional[InterventionId] = None
    booking_id: Optional[BookingId] = None
    job_id: Optional[JobId] = None
    revenue_record_id: Optional[RevenueRecordId] = None
    attribution_id: Optional[AttributionId] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def can_transition_to(self, target_state: OpportunityState) -> bool:
        """Check if transition to target state is valid.
        
        Args:
            target_state: Target state
            
        Returns:
            True if transition is allowed
        """
        # Import here to avoid circular dependency
        from .state_machine import StateTransitionRule

        return StateTransitionRule.can_transition(self.state, target_state)

    def transition(
        self,
        target_state: OpportunityState,
        reason: Optional[str] = None,
    ) -> None:
        """Transition opportunity to a new state.
        
        Args:
            target_state: Target state
            reason: Optional reason for transition (e.g., blocked_reason)
            
        Raises:
            RevenueOpportunityError: If transition is invalid
        """
        # Import here to avoid circular dependency
        from .state_machine import StateTransitionRule, InvalidTransitionError

        try:
            StateTransitionRule.validate_transition(self.state, target_state)
        except InvalidTransitionError as e:
            raise RevenueOpportunityError(str(e))

        # Update state and timestamp
        self.state = target_state
        self.updated_at = datetime.utcnow()

        # Store reason if applicable
        if target_state == OpportunityState.BLOCKED and reason:
            self.blocked_reason = reason
        elif target_state == OpportunityState.ELIGIBLE and reason:
            self.eligible_reason = reason


@dataclass
class Booking:
    """Represents a confirmed booking tied to an opportunity.
    
    FACT: Booking exists independently but can be linked to opportunity.
    ASSUMPTION: External system (Jobber/ServiceTitan) owns booking details.
    DECISION: Track only critical fields; reference external IDs.
    
    DESIGN: booking_origin and external_created_at distinguish
    pre-existing bookings from recovery-created bookings.
    """

    booking_id: BookingId
    tenant_id: TenantId
    customer_id: CustomerId
    external_booking_id: str  # e.g., Jobber booking ID
    scheduled_at: datetime
    booking_origin: BookingOrigin
    created_at: datetime  # When OUR SYSTEM recorded the booking
    updated_at: datetime
    opportunity_id: Optional[OpportunityId] = None
    external_created_at: Optional[datetime] = None  # When external system created it
    cancelled_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate booking invariants."""
        if self.booking_origin == BookingOrigin.EXISTING:
            if self.external_created_at is None:
                raise ValueError(
                    "EXISTING bookings must have external_created_at timestamp"
                )
        elif self.booking_origin == BookingOrigin.RECOVERY:
            # Recovery bookings may or may not have external_created_at
            pass
        # UNKNOWN origin allows both states


@dataclass
class Job:
    """Represents a service job with explicit status.
    
    FACT: Job completion is prerequisite for revenue attribution.
    ASSUMPTION: External system owns job details.
    DECISION: Explicit status field; completed_at required if COMPLETED.
    """

    job_id: JobId
    booking_id: BookingId
    tenant_id: TenantId
    customer_id: CustomerId
    external_job_id: str  # e.g., Jobber job ID
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate job invariants."""
        if self.status == JobStatus.COMPLETED:
            if self.completed_at is None:
                raise ValueError(
                    "Completed jobs must have completed_at timestamp"
                )
        elif self.status == JobStatus.PENDING:
            if self.completed_at is not None:
                raise ValueError(
                    "Pending jobs cannot have completed_at timestamp"
                )
        elif self.status == JobStatus.CANCELLED:
            pass  # cancelled_at is optional


@dataclass(frozen=True)
class RevenueRecord:
    """Immutable record of revenue associated with a job.
    
    FACT: Revenue data comes from external system (Jobber/ServiceTitan).
    ASSUMPTION: Never assume revenue; only record what's reported.
    DECISION: Track gross revenue and gross profit separately.
    UNKNOWN: Cost basis - passed from external system or None.
    
    NOTE: opportunity_id is OPTIONAL. Revenue exists independently.
    Attribution layer determines if this revenue is attributable.
    """

    revenue_record_id: RevenueRecordId
    job_id: JobId
    booking_id: BookingId
    tenant_id: TenantId
    customer_id: CustomerId
    gross_revenue: Money
    gross_profit: Optional[Money] = None  # May be unknown initially
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    opportunity_id: Optional[OpportunityId] = None  # Optional: set by attribution

    def __post_init__(self) -> None:
        """Validate revenue record."""
        if self.gross_revenue.amount_cents < 0:
            raise ValueError("gross_revenue cannot be negative")
        if self.gross_profit is not None:
            if self.gross_profit.currency != self.gross_revenue.currency:
                raise ValueError(
                    "gross_profit must use same currency as gross_revenue"
                )


class AttributionError(Exception):
    """Raised when attribution invariants are violated."""

    pass


@dataclass(frozen=True)
class Attribution:
    """Represents the attribution of revenue to an opportunity.
    
    FACT: Attribution is deterministic, based on evidence.
    ASSUMPTION: Evidence is a list of event IDs that establish causality.
    DECISION: Rejection is final; reasons must be explicit.
    
    INVARIANTS:
    - APPROVED + DIRECT => intervention_id, booking_id, job_id, revenue_record_id required
    - APPROVED + ASSISTED => same + human_escalation evidence required
    - UNKNOWN => incomplete evidence allowed
    - REJECTED => rejection_reason must be set
    - evidence_event_ids must be non-empty for APPROVED
    """

    attribution_id: AttributionId
    opportunity_id: OpportunityId
    tenant_id: TenantId
    attribution_type: AttributionType
    status: AttributionStatus
    confidence: int  # 0-100, meaningful for UNKNOWN
    evidence_event_ids: tuple[EventId, ...]
    reason: Optional[str] = None
    intervention_id: Optional[InterventionId] = None
    booking_id: Optional[BookingId] = None
    job_id: Optional[JobId] = None
    revenue_record_id: Optional[RevenueRecordId] = None
    rejection_reason: Optional[RejectionReason] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate attribution invariants."""
        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

        if self.status == AttributionStatus.APPROVED:
            if self.attribution_type == AttributionType.DIRECT:
                if not all(
                    [
                        self.intervention_id,
                        self.booking_id,
                        self.job_id,
                        self.revenue_record_id,
                    ]
                ):
                    raise AttributionError(
                        "APPROVED DIRECT attribution requires intervention_id, "
                        "booking_id, job_id, and revenue_record_id"
                    )
            elif self.attribution_type == AttributionType.ASSISTED:
                if not all(
                    [
                        self.intervention_id,
                        self.booking_id,
                        self.job_id,
                        self.revenue_record_id,
                    ]
                ):
                    raise AttributionError(
                        "APPROVED ASSISTED attribution requires intervention_id, "
                        "booking_id, job_id, and revenue_record_id"
                    )
            if not self.evidence_event_ids:
                raise AttributionError(
                    "APPROVED attribution must have evidence_event_ids"
                )
        elif self.status == AttributionStatus.REJECTED:
            if self.rejection_reason is None:
                raise AttributionError(
                    "REJECTED attribution must have rejection_reason"
                )
