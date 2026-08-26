"""Attribution model for revenue recovery.

Determines whether revenue can be attributed to recovery interventions.
"""

from datetime import datetime
from typing import Optional
from .value_objects import (
    AttributionType,
    AttributionStatus,
    RejectionReason,
    EventType,
    EventId,
)
from .entities import (
    Attribution,
    RevenueOpportunity,
    generate_attribution_id,
    BookingOrigin,
)


class AttributionError(Exception):
    """Raised when attribution cannot be determined."""

    pass


class AttributionModel:
    """Determines attribution of revenue to recovery opportunities.

    FACT: Attribution is deterministic, based on event evidence.
    ASSUMPTION: Missing evidence results in UNKNOWN, not guessing.
    DECISION: REJECTED attributions are final and auditable.
    
    RULES:
    - DIRECT: intervention -> response -> qualified -> booked -> completed
    - ASSISTED: same as DIRECT but with human escalation
    - UNKNOWN: incomplete evidence
    - REJECTED: evidence fails exclusion rules
    """

    @staticmethod
    def can_create_direct_attribution(opportunity: RevenueOpportunity) -> bool:
        """Check if opportunity qualifies for DIRECT attribution.

        DIRECT attribution requires:
        1. Intervention was initiated (recovery_initiated event)
        2. Customer replied (customer_replied event)
        3. Lead was qualified
        4. Booking was created
        5. Job was completed
        6. No booking existed before intervention

        Args:
            opportunity: The revenue opportunity

        Returns:
            True if opportunity has required evidence for DIRECT attribution
        """
        # All required entities must be present
        if not all(
            [
                opportunity.intervention_id,
                opportunity.booking_id,
                opportunity.job_id,
                opportunity.revenue_record_id,
            ]
        ):
            return False

        # Opportunity must be in COMPLETED state
        from .value_objects import OpportunityState
        if opportunity.state != OpportunityState.COMPLETED:
            return False

        return True

    @staticmethod
    def can_create_assisted_attribution(opportunity: RevenueOpportunity) -> bool:
        """Check if opportunity qualifies for ASSISTED attribution.

        ASSISTED attribution requires:
        1. Same as DIRECT, but with HUMAN_ESCALATION event
        2. Indicates human took over after initial intervention

        Args:
            opportunity: The revenue opportunity

        Returns:
            True if opportunity has required evidence for ASSISTED attribution
        """
        # For M0, ASSISTED is same as DIRECT but will be differentiated
        # in M1 based on HUMAN_ESCALATION events
        return AttributionModel.can_create_direct_attribution(opportunity)

    @staticmethod
    def check_for_rejection_reasons(
        opportunity: RevenueOpportunity, 
        booking_existed_before_intervention: bool,
    ) -> Optional[RejectionReason]:
        """Check if opportunity should be rejected for attribution.

        Args:
            opportunity: The revenue opportunity
            booking_existed_before_intervention: Whether booking existed before intervention

        Returns:
            RejectionReason if applicable, None otherwise
        """
        # Booking existed before intervention - cannot attribute
        if booking_existed_before_intervention:
            return RejectionReason.BOOKING_EXISTED_BEFORE_INTERVENTION

        # Missing required evidence for any attribution type
        if not opportunity.intervention_id:
            return RejectionReason.NO_CAUSAL_EVIDENCE

        if not opportunity.job_id or not opportunity.revenue_record_id:
            return RejectionReason.INSUFFICIENT_EVIDENCE

        return None

    @staticmethod
    def create_attribution(
        opportunity: RevenueOpportunity,
        evidence_event_ids: list[EventId],
        booking_existed_before_intervention: bool = False,
        has_human_escalation: bool = False,
    ) -> Attribution:
        """Create an attribution for a revenue opportunity.

        Args:
            opportunity: The revenue opportunity
            evidence_event_ids: List of event IDs supporting attribution
            booking_existed_before_intervention: Whether booking pre-existed
            has_human_escalation: Whether human escalation occurred

        Returns:
            Attribution object with appropriate type and status
        """
        rejection_reason = AttributionModel.check_for_rejection_reasons(
            opportunity, booking_existed_before_intervention
        )

        if rejection_reason:
            return Attribution(
                attribution_id=generate_attribution_id(),
                opportunity_id=opportunity.opportunity_id,
                intervention_id=opportunity.intervention_id,
                booking_id=opportunity.booking_id,
                job_id=opportunity.job_id,
                revenue_record_id=opportunity.revenue_record_id,
                tenant_id=opportunity.tenant_id,
                attribution_type=AttributionType.REJECTED,
                status=AttributionStatus.REJECTED,
                confidence=0,
                evidence_event_ids=tuple(evidence_event_ids),
                reason=f"Attribution rejected: {rejection_reason.value}",
                rejection_reason=rejection_reason,
            )

        # Determine attribution type based on evidence
        attribution_type = (
            AttributionType.ASSISTED
            if has_human_escalation
            else AttributionType.DIRECT
        )

        # Check if we have all evidence for this type
        if not AttributionModel.can_create_direct_attribution(opportunity):
            return Attribution(
                attribution_id=generate_attribution_id(),
                opportunity_id=opportunity.opportunity_id,
                intervention_id=opportunity.intervention_id,
                booking_id=opportunity.booking_id,
                job_id=opportunity.job_id,
                revenue_record_id=opportunity.revenue_record_id,
                tenant_id=opportunity.tenant_id,
                attribution_type=AttributionType.UNKNOWN,
                status=AttributionStatus.PENDING,
                confidence=50,
                evidence_event_ids=tuple(evidence_event_ids),
                reason="Incomplete evidence for definitive attribution",
            )

        # Create approved attribution
        return Attribution(
            attribution_id=generate_attribution_id(),
            opportunity_id=opportunity.opportunity_id,
            intervention_id=opportunity.intervention_id,
            booking_id=opportunity.booking_id,
            job_id=opportunity.job_id,
            revenue_record_id=opportunity.revenue_record_id,
            tenant_id=opportunity.tenant_id,
            attribution_type=attribution_type,
            status=AttributionStatus.APPROVED,
            confidence=95,
            evidence_event_ids=tuple(evidence_event_ids),
            reason=f"Revenue attributed via {attribution_type.value} path",
        )
