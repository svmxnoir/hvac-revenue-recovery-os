"""Value objects with strong typing and validation."""

from dataclasses import dataclass
from datetime import datetime
from typing import NewType
from enum import Enum
import uuid


# Strong IDs
TenantId = NewType("TenantId", str)
CustomerId = NewType("CustomerId", str)
OpportunityId = NewType("OpportunityId", str)
EventId = NewType("EventId", str)
InterventionId = NewType("InterventionId", str)
BookingId = NewType("BookingId", str)
JobId = NewType("JobId", str)
RevenueRecordId = NewType("RevenueRecordId", str)
AttributionId = NewType("AttributionId", str)


def generate_tenant_id() -> TenantId:
    """Generate a new tenant ID."""
    return TenantId(f"TEN-{uuid.uuid4().hex[:12].upper()}")


def generate_opportunity_id(tenant_id: TenantId, sequence: int) -> OpportunityId:
    """Generate a stable opportunity ID: RR-{YEAR}-{SEQUENCE}."""
    year = datetime.utcnow().year
    return OpportunityId(f"RR-{year}-{sequence:08d}")


def generate_event_id() -> EventId:
    """Generate a new event ID."""
    return EventId(str(uuid.uuid4()))


def generate_intervention_id() -> InterventionId:
    """Generate a new intervention ID."""
    return InterventionId(str(uuid.uuid4()))


def generate_booking_id() -> BookingId:
    """Generate a new booking ID."""
    return BookingId(str(uuid.uuid4()))


def generate_job_id() -> JobId:
    """Generate a new job ID."""
    return JobId(str(uuid.uuid4()))


def generate_revenue_record_id() -> RevenueRecordId:
    """Generate a new revenue record ID."""
    return RevenueRecordId(str(uuid.uuid4()))


def generate_attribution_id() -> AttributionId:
    """Generate a new attribution ID."""
    return AttributionId(str(uuid.uuid4()))


class EventType(str, Enum):
    """Enumeration of all event types in the system."""

    # Call events
    CALL_RECEIVED = "CALL_RECEIVED"
    CALL_MISSED = "CALL_MISSED"
    CALL_ANSWERED = "CALL_ANSWERED"

    # Recovery events
    RECOVERY_ELIGIBILITY_CHECKED = "RECOVERY_ELIGIBILITY_CHECKED"
    RECOVERY_BLOCKED = "RECOVERY_BLOCKED"
    RECOVERY_INITIATED = "RECOVERY_INITIATED"
    MESSAGE_SENT = "MESSAGE_SENT"
    MESSAGE_DELIVERED = "MESSAGE_DELIVERED"
    CUSTOMER_REPLIED = "CUSTOMER_REPLIED"

    # Classification events
    LEAD_CLASSIFIED = "LEAD_CLASSIFIED"
    LEAD_QUALIFIED = "LEAD_QUALIFIED"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"

    # Availability events
    AVAILABILITY_REQUESTED = "AVAILABILITY_REQUESTED"
    AVAILABILITY_CONFIRMED = "AVAILABILITY_CONFIRMED"
    AVAILABILITY_FAILED = "AVAILABILITY_FAILED"

    # Booking events
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"

    # Job events
    JOB_CREATED = "JOB_CREATED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_CANCELLED = "JOB_CANCELLED"

    # Revenue events
    REVENUE_RECORDED = "REVENUE_RECORDED"

    # Attribution events
    ATTRIBUTION_CREATED = "ATTRIBUTION_CREATED"
    ATTRIBUTION_REJECTED = "ATTRIBUTION_REJECTED"

    # Consent events
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    OPT_OUT_RECEIVED = "OPT_OUT_RECEIVED"


class OpportunityState(str, Enum):
    """Revenue opportunity lifecycle states."""

    DETECTED = "DETECTED"
    ELIGIBILITY_PENDING = "ELIGIBILITY_PENDING"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    QUALIFIED = "QUALIFIED"
    BOOKING_PENDING = "BOOKING_PENDING"
    BOOKED = "BOOKED"
    COMPLETED = "COMPLETED"
    LOST = "LOST"
    CANCELLED = "CANCELLED"


class ConsentStatus(str, Enum):
    """Compliance consent states."""

    UNKNOWN = "UNKNOWN"
    ELIGIBLE = "ELIGIBLE"
    SUPPRESSED = "SUPPRESSED"
    OPTED_OUT = "OPTED_OUT"


class MessagePurpose(str, Enum):
    """Classification of message purpose."""

    SERVICE_RECOVERY = "SERVICE_RECOVERY"
    TRANSACTIONAL = "TRANSACTIONAL"
    MARKETING = "MARKETING"


class AttributionType(str, Enum):
    """Attribution classification."""

    DIRECT = "DIRECT"
    ASSISTED = "ASSISTED"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class AttributionStatus(str, Enum):
    """Attribution validation status."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RejectionReason(str, Enum):
    """Reasons for attribution rejection."""

    BOOKING_EXISTED_BEFORE_INTERVENTION = "BOOKING_EXISTED_BEFORE_INTERVENTION"
    NO_CAUSAL_EVIDENCE = "NO_CAUSAL_EVIDENCE"
    DUPLICATE_OPPORTUNITY = "DUPLICATE_OPPORTUNITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REVENUE_CANNOT_BE_CONNECTED = "REVENUE_CANNOT_BE_CONNECTED"
    OTHER = "OTHER"


@dataclass(frozen=True)
class Money:
    """Represents monetary value with currency.
    
    FACT: Money is stored as a decimal value.
    ASSUMPTION: Currency defaults to USD.
    DECISION: Use dataclass for immutability.
    """

    amount_cents: int  # Store as cents to avoid float precision issues
    currency: str = "USD"

    @property
    def amount_dollars(self) -> float:
        """Return amount in dollars."""
        return self.amount_cents / 100.0

    @staticmethod
    def from_dollars(dollars: float, currency: str = "USD") -> "Money":
        """Create Money from dollar amount."""
        return Money(int(dollars * 100), currency)

    def __str__(self) -> str:
        return f"${self.amount_dollars:.2f} {self.currency}"


@dataclass(frozen=True)
class IntentInterpretation:
    """Result of AI interpretation of customer intent.
    
    FACT: This is advisory only. Domain rules remain deterministic.
    ASSUMPTION: Confidence is 0-100.
    DECISION: Include unknown_fields to preserve uninterpreted data.
    """

    intent: str
    service_category: str
    urgency: str  # e.g., "HIGH", "MEDIUM", "LOW"
    customer_goal: str
    confidence: int  # 0-100
    unknown_fields: dict[str, any] | None = None
