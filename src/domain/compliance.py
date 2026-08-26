"""Compliance and consent management.

Enforces opt-out recognition, suppression rules, and message purpose classification.
"""

from datetime import datetime
from typing import Optional
from .value_objects import ConsentStatus, MessagePurpose
from .entities import ConsentState, CustomerId, TenantId


# Patterns that indicate opt-out
OPT_OUT_KEYWORDS = {
    "STOP",
    "UNSUBSCRIBE",
    "CANCEL",
    "END",
    "QUIT",
    "REVOKE",
    "OPT OUT",
    "OPT-OUT",
    "REMOVE",
}


class ComplianceError(Exception):
    """Raised when compliance rules are violated."""

    pass


class ComplianceModel:
    """Manages consent states and opt-out enforcement.

    FACT: Opt-out is permanent unless explicitly revoked.
    ASSUMPTION: Message content is checked for opt-out keywords.
    DECISION: Opt-out blocks intervention before sending.
    
    SEMANTICS:
    - CONSENT_GRANTED: customer explicitly grants consent
    - CONSENT_REVOKED: previously granted consent is revoked
    - OPT_OUT_RECEIVED: explicit opt-out signal was received
    """

    @staticmethod
    def extract_opt_out_signal(message: str) -> bool:
        """Check if message contains opt-out signal.
        
        Performs case-insensitive word boundary matching.
        Normalizes whitespace and punctuation.

        Args:
            message: Customer message text

        Returns:
            True if message contains opt-out keyword, False otherwise
        """
        if not message:
            return False

        # Normalize: uppercase, remove punctuation, split on whitespace
        normalized = message.upper()
        # Replace common punctuation with spaces
        for char in ".,!?;:-()":
            normalized = normalized.replace(char, " ")
        # Split into words
        words = normalized.split()
        
        # Check for opt-out keywords
        return any(word in OPT_OUT_KEYWORDS for word in words)

    @staticmethod
    def can_send_intervention(consent_state: ConsentState) -> bool:
        """Determine if intervention can be sent to customer.

        Args:
            consent_state: Customer's current consent state

        Returns:
            True if intervention can be sent, False if suppressed or opted out
        """
        if consent_state.consent_status == ConsentStatus.OPTED_OUT:
            return False
        if consent_state.consent_status == ConsentStatus.SUPPRESSED:
            return False
        return consent_state.consent_status in (
            ConsentStatus.ELIGIBLE,
            ConsentStatus.UNKNOWN,
        )

    @staticmethod
    def validate_intervention_can_send(consent_state: ConsentState) -> None:
        """Validate that intervention can be sent, raising if blocked.

        Args:
            consent_state: Customer's current consent state

        Raises:
            ComplianceError: If intervention is blocked by compliance rules
        """
        if not ComplianceModel.can_send_intervention(consent_state):
            reason = (
                "opted out"
                if consent_state.consent_status == ConsentStatus.OPTED_OUT
                else f"suppressed ({consent_state.suppression_reason})"
            )
            raise ComplianceError(
                f"Cannot send intervention: customer has {reason}"
            )

    @staticmethod
    def handle_opt_out(
        consent_state: ConsentState,
    ) -> ConsentState:
        """Update consent state when opt-out signal is received.

        Args:
            consent_state: Current consent state

        Returns:
            Updated consent state with OPTED_OUT status
        """
        return ConsentState(
            customer_id=consent_state.customer_id,
            tenant_id=consent_state.tenant_id,
            consent_status=ConsentStatus.OPTED_OUT,
            consent_source="OPT_OUT_RECEIVED",
            consent_timestamp=None,
            opt_out_timestamp=datetime.utcnow(),
            suppression_reason="Customer opt-out",
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def handle_consent_granted(
        customer_id: CustomerId,
        tenant_id: TenantId,
        source: Optional[str] = None,
    ) -> ConsentState:
        """Create a consent state when consent is explicitly granted.

        Args:
            customer_id: Customer ID
            tenant_id: Tenant ID
            source: Source of consent (e.g., "EXPLICIT_GRANT", "FORM_SUBMISSION")

        Returns:
            New ConsentState with ELIGIBLE status
        """
        return ConsentState(
            customer_id=customer_id,
            tenant_id=tenant_id,
            consent_status=ConsentStatus.ELIGIBLE,
            consent_source=source or "EXPLICIT_GRANT",
            consent_timestamp=datetime.utcnow(),
            opt_out_timestamp=None,
            suppression_reason=None,
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def handle_consent_revoked(
        consent_state: ConsentState,
    ) -> ConsentState:
        """Update consent state when previously granted consent is revoked.

        Args:
            consent_state: Current consent state

        Returns:
            Updated consent state with SUPPRESSED status
        """
        return ConsentState(
            customer_id=consent_state.customer_id,
            tenant_id=consent_state.tenant_id,
            consent_status=ConsentStatus.SUPPRESSED,
            consent_source="CONSENT_REVOKED",
            consent_timestamp=None,
            opt_out_timestamp=datetime.utcnow(),
            suppression_reason="Consent was revoked",
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def classify_message_purpose(
        message_content: str, intervention_type: Optional[str] = None
    ) -> MessagePurpose:
        """Classify the purpose of a message.

        Args:
            message_content: The message content
            intervention_type: Type of intervention (if known)

        Returns:
            MessagePurpose enum

        Note: M0 only implements SERVICE_RECOVERY. Marketing and transactional
        classification will be added in later milestones.
        """
        # M0: Default to SERVICE_RECOVERY for recovery interventions
        # TODO: Implement sophisticated classification in M1
        return MessagePurpose.SERVICE_RECOVERY
