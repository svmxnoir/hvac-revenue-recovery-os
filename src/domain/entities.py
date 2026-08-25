"""Core domain entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
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
    EventType,
    OpportunityState,
    ConsentStatus,
    MessagePurpose,
    AttributionType,
    AttributionStatus,
    RejectionReason,
    Money,
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


@dataclass
class Event:
    """Immutable event record in the append-only ledger.
    
    FACT: Events are immutable and ordered by recorded_at.
    ASSUMPTION: source_event_id enables idempotency.
    DECISION: payload is flexible dict to support any event type.
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
    payload: dict[str, Any]
    schema_version: str = "1.0"


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

    conversation_id: str
    intervention_id: InterventionId
    tenant_id: TenantId
    customer_id: CustomerId
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RevenueOpportunity:
    """Core entity representing a potential revenue recovery.
    
    FACT: Lifecycle spans from detected to completed or lost.
    ASSUMPTION: State transitions are deterministic.
    DECISION: Track all related entities for auditing and attribution.
    """

    opportunity_id: OpportunityId
    tenant_id: TenantId
    customer_id: CustomerId
    state: OpportunityState
    missed_call_at: datetime
    detected_at: datetime
    eligible_reason: Optional[str]
    blocked_reason: Optional[str]
    intervention_id: Optional[InterventionId] = None
    booking_id: Optional[BookingId] = None
    job_id: Optional[JobId] = None
    revenue_record_id: Optional[RevenueRecordId] = None
    attribution_id: Optional[AttributionId] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Booking:
    """Represents a confirmed booking tied to an opportunity.
    
    FACT: Booking exists independently but can be linked to opportunity.
    ASSUMPTION: External system (Jobber/ServiceTitan) owns booking details.
    DECISION: Track only critical fields; reference external IDs.
    """

    booking_id: BookingId
    opportunity_id: Optional[OpportunityId]
    tenant_id: TenantId
    customer_id: CustomerId
    external_booking_id: str  # e.g., Jobber booking ID
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime
    cancelled_at: Optional[datetime] = None


@dataclass
class Job:
    """Represents a completed (or in-progress) service job.
    
    FACT: Job completion is prerequisite for revenue attribution.
    ASSUMPTION: External system owns job details.
    DECISION: Track only ID, status, and revenue link.
    """

    job_id: JobId
    booking_id: BookingId
    tenant_id: TenantId
    customer_id: CustomerId
    external_job_id: str  # e.g., Jobber job ID
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass
class RevenueRecord:
    """Immutable record of revenue associated with a job.
    
    FACT: Revenue data comes from external system (Jobber/ServiceTitan).
    ASSUMPTION: Never assume revenue; only record what's reported.
    DECISION: Track gross revenue and gross profit separately.
    UNKNOWN: Cost basis - passed from external system or None.
    """

    revenue_record_id: RevenueRecordId
    job_id: JobId
    booking_id: BookingId
    tenant_id: TenantId
    customer_id: CustomerId
    gross_revenue: Money
    gross_profit: Optional[Money]  # May be unknown initially
    recorded_at: datetime
    created_at: datetime


@dataclass
class Attribution:
    """Represents the attribution of revenue to an opportunity.
    
    FACT: Attribution is deterministic, based on evidence.
    ASSUMPTION: Evidence is a list of event IDs that establish causality.
    DECISION: Rejection is final; reasons must be explicit.
    """

    attribution_id: AttributionId
    opportunity_id: OpportunityId
    intervention_id: Optional[InterventionId]
    booking_id: Optional[BookingId]
    job_id: Optional[JobId]
    revenue_record_id: Optional[RevenueRecordId]
    tenant_id: TenantId
    attribution_type: AttributionType
    status: AttributionStatus
    confidence: int  # 0-100, meaningful for UNKNOWN
    evidence_event_ids: list[EventId]
    reason: Optional[str]  # For REJECTED attributions
    rejection_reason: Optional[RejectionReason] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
