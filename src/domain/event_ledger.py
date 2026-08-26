"""Append-only event ledger for auditability and idempotency."""

from datetime import datetime
from typing import Optional
from .value_objects import (
    EventId,
    TenantId,
    EventType,
    generate_event_id,
)
from .entities import Event


class DuplicateEventError(Exception):
    """Raised when attempting to record a duplicate event."""

    pass


class EventLedger:
    """Append-only ledger for recording events.

    FACT: Events are immutable and ordered by recorded_at.
    ASSUMPTION: Idempotency key is (tenant_id, source, source_event_id).
    DECISION: In-memory storage for M0; production uses database.
    
    NOTE: Out-of-order events (by occurred_at) are recorded in order received.
    Reconciliation of out-of-order events happens at processing layer,
    not in the ledger.
    """

    def __init__(self) -> None:
        """Initialize the event ledger."""
        self.events: list[Event] = []
        # Track seen idempotency keys to detect duplicates
        # Key: (tenant_id, source, source_event_id)
        self.seen_keys: set[tuple[str, str, str]] = set()

    def append(
        self,
        tenant_id: TenantId,
        event_type: EventType,
        occurred_at: datetime,
        source: str,
        source_event_id: str,
        entity_type: str,
        entity_id: str,
        payload: dict,
        event_id: Optional[EventId] = None,
        recorded_at: Optional[datetime] = None,
    ) -> Event:
        """Append an event to the ledger.

        Args:
            tenant_id: Tenant ID
            event_type: Type of event
            occurred_at: When the event occurred
            source: Source system (e.g., "TWILIO")
            source_event_id: External event ID for idempotency
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            payload: Event payload
            event_id: Event ID (generated if not provided)
            recorded_at: When event was recorded (defaults to now)

        Returns:
            The recorded Event

        Raises:
            DuplicateEventError: If event with same idempotency key already exists
        """
        # Check for duplicate using idempotency key
        idempotency_key = (str(tenant_id), source, source_event_id)
        if idempotency_key in self.seen_keys:
            raise DuplicateEventError(
                f"Event already exists: {idempotency_key}. This is idempotent - no new event recorded."
            )

        event_id = event_id or generate_event_id()
        recorded_at = recorded_at or datetime.utcnow()

        # Create event with frozen payload
        event = Event.create(
            event_id=event_id,
            tenant_id=tenant_id,
            event_type=event_type,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            source=source,
            source_event_id=source_event_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )

        self.events.append(event)
        self.seen_keys.add(idempotency_key)
        return event

    def get_events(
        self, tenant_id: TenantId, entity_id: Optional[str] = None
    ) -> list[Event]:
        """Retrieve events for a tenant or specific entity.

        Args:
            tenant_id: Tenant ID
            entity_id: Optional specific entity ID

        Returns:
            List of events ordered by recorded_at (arrival order)
        """
        events = [e for e in self.events if e.tenant_id == tenant_id]
        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]
        return sorted(events, key=lambda e: e.recorded_at)

    def get_events_by_occurrence(
        self, tenant_id: TenantId, entity_id: Optional[str] = None
    ) -> list[Event]:
        """Retrieve events ordered by occurrence time (not arrival time).
        
        Useful for reconciling out-of-order events.

        Args:
            tenant_id: Tenant ID
            entity_id: Optional specific entity ID

        Returns:
            List of events ordered by occurred_at
        """
        events = [e for e in self.events if e.tenant_id == tenant_id]
        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]
        return sorted(events, key=lambda e: e.occurred_at)

    def has_event(
        self, tenant_id: TenantId, source: str, source_event_id: str
    ) -> bool:
        """Check if an event has already been recorded.

        Args:
            tenant_id: Tenant ID
            source: Source system
            source_event_id: External event ID

        Returns:
            True if event exists, False otherwise
        """
        idempotency_key = (str(tenant_id), source, source_event_id)
        return idempotency_key in self.seen_keys
