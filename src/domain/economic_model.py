"""Economic measurement model.

Calculates metrics and KPIs for revenue recovery performance.

CRITICAL DESIGN PRINCIPLES:

1. REVENUE DISTINCTION
   - Observed revenue: What external system reports
   - Attributable revenue: What domain rules connect to recovery
   - Recovered revenue: Attributable revenue that is realized
   - These are NOT interchangeable

2. MISSING DATA HANDLING
   - If required calculation data is missing, return None
   - Never silently substitute zero
   - Never invent financial values
   - Explicitly document missing data requirements

3. RATE CALCULATIONS
   - numerator / denominator
   - If denominator == 0, return None
   - Do not fabricate rates
   - Document exactly what counts in numerator and denominator

4. NO AI JUDGMENT
   - Economic calculations are deterministic
   - No interpretation or guessing
   - No default values
"""

from typing import Optional
from .value_objects import Money, OpportunityState
from .entities import RevenueOpportunity, RevenueRecord, Attribution, Job, JobStatus


class EconomicModel:
    """Calculates economic metrics for revenue recovery.

    FACT: Metrics are calculated from actual recorded data.
    ASSUMPTION: Never hardcode benchmarks or fictional values.
    DECISION: Missing data is represented as None, not guessed.
    """

    # ========================================================================
    # RATE CALCULATIONS
    # ========================================================================

    @staticmethod
    def calculate_missed_call_rate(
        total_calls: int, missed_calls: int
    ) -> Optional[float]:
        """Calculate missed call rate.

        Definition:
        - numerator: count of CALL_MISSED events
        - denominator: count of CALL_RECEIVED + CALL_MISSED events (total inbound)
        - result: percentage of missed calls

        Args:
            total_calls: Total number of inbound calls (CALL_RECEIVED + CALL_MISSED)
            missed_calls: Number of missed calls (CALL_MISSED)

        Returns:
            Missed call rate as percentage (0-100) or None if no data
        """
        if total_calls == 0:
            return None
        return (missed_calls / total_calls) * 100

    @staticmethod
    def calculate_recovery_rate(
        missed_calls: int, recovery_attempts: int
    ) -> Optional[float]:
        """Calculate recovery intervention rate.

        Definition:
        - numerator: count of RECOVERY_INITIATED events
        - denominator: count of CALL_MISSED events
        - result: percentage of missed calls where recovery was attempted
        - NOTE: This is NOT attribution rate; it's intervention rate

        Args:
            missed_calls: Number of missed calls
            recovery_attempts: Number of recovery interventions initiated

        Returns:
            Recovery rate as percentage (0-100) or None if no data
        """
        if missed_calls == 0:
            return None
        return (recovery_attempts / missed_calls) * 100

    @staticmethod
    def calculate_engagement_rate(
        interventions_sent: int, customer_replies: int
    ) -> Optional[float]:
        """Calculate customer engagement rate.

        Definition:
        - numerator: count of CUSTOMER_REPLIED events
        - denominator: count of MESSAGE_SENT events
        - result: percentage of interventions that customer responded to
        - NOTE: Requires MESSAGE_DELIVERED before customer reply

        Args:
            interventions_sent: Number of interventions sent
            customer_replies: Number of customer responses

        Returns:
            Engagement rate as percentage (0-100) or None if no data
        """
        if interventions_sent == 0:
            return None
        return (customer_replies / interventions_sent) * 100

    @staticmethod
    def calculate_qualification_rate(
        engaged_leads: int, qualified_leads: int
    ) -> Optional[float]:
        """Calculate lead qualification rate.

        Definition:
        - numerator: count of LEAD_QUALIFIED events
        - denominator: count of opportunities in ENGAGED or beyond state
        - result: percentage of engaged leads that qualified

        Args:
            engaged_leads: Number of engaged leads
            qualified_leads: Number of qualified leads

        Returns:
            Qualification rate as percentage (0-100) or None if no data
        """
        if engaged_leads == 0:
            return None
        return (qualified_leads / engaged_leads) * 100

    @staticmethod
    def calculate_booking_rate(
        qualified_leads: int, bookings: int
    ) -> Optional[float]:
        """Calculate booking conversion rate.

        Definition:
        - numerator: count of BOOKING_CREATED events linked to opportunities
        - denominator: count of opportunities in QUALIFIED or beyond state
        - result: percentage of qualified leads that became bookings

        Args:
            qualified_leads: Number of qualified leads
            bookings: Number of bookings created

        Returns:
            Booking rate as percentage (0-100) or None if no data
        """
        if qualified_leads == 0:
            return None
        return (bookings / qualified_leads) * 100

    @staticmethod
    def calculate_completion_rate(
        bookings: int, completed_jobs: int
    ) -> Optional[float]:
        """Calculate job completion rate.

        Definition:
        - numerator: count of JOB_COMPLETED events (or Job.status == COMPLETED)
        - denominator: count of Booking entities
        - result: percentage of bookings with completed jobs
        - NOTE: Booking cancellation reduces denominator

        Args:
            bookings: Number of bookings
            completed_jobs: Number of completed jobs

        Returns:
            Completion rate as percentage (0-100) or None if no data
        """
        if bookings == 0:
            return None
        return (completed_jobs / bookings) * 100

    # ========================================================================
    # REVENUE CALCULATIONS
    # ========================================================================

    @staticmethod
    def calculate_observed_revenue(
        revenue_records: list[RevenueRecord],
    ) -> Optional[Money]:
        """Calculate total observed revenue from all revenue records.

        Definition:
        - Sum of all RevenueRecord.gross_revenue values
        - Does NOT filter by attribution
        - Represents total revenue reported by external system
        - NOTE: This is raw input data, not necessarily attributable

        Args:
            revenue_records: List of all revenue records

        Returns:
            Total observed revenue or None if no records
        """
        if not revenue_records:
            return None

        # Verify all records use same currency
        currencies = {r.gross_revenue.currency for r in revenue_records}
        if len(currencies) > 1:
            raise ValueError("Cannot sum revenue with mixed currencies")

        total_cents = sum(r.gross_revenue.amount_cents for r in revenue_records)
        currency = revenue_records[0].gross_revenue.currency
        return Money(total_cents, currency)

    @staticmethod
    def calculate_attributable_revenue(
        attributions: list[Attribution],
        revenue_records: dict[str, RevenueRecord],  # keyed by revenue_record_id
    ) -> Optional[Money]:
        """Calculate total attributable revenue from APPROVED attributions.

        Definition:
        - Sum of RevenueRecord.gross_revenue for APPROVED attributions only
        - Requires Attribution.status == APPROVED
        - Requires Attribution.revenue_record_id to resolve to actual record
        - REJECTED and UNKNOWN attributions excluded
        - NOTE: Attributable ≠ realized; still dependent on job completion

        Args:
            attributions: List of attribution objects
            revenue_records: Dict mapping revenue_record_id (str) to RevenueRecord

        Returns:
            Total attributable revenue or None if no approved attributions
        """
        from .value_objects import AttributionStatus

        approved = [
            a for a in attributions if a.status == AttributionStatus.APPROVED
        ]
        if not approved:
            return None

        # Collect revenue records for approved attributions
        total_cents = 0
        currency = None

        for attribution in approved:
            if not attribution.revenue_record_id:
                # Approved attribution without revenue record is invalid
                raise ValueError(
                    f"Approved attribution {attribution.attribution_id} "
                    "has no revenue_record_id"
                )

            record_id_str = str(attribution.revenue_record_id)
            if record_id_str not in revenue_records:
                # Revenue record not found (missing evidence)
                continue

            record = revenue_records[record_id_str]
            if currency is None:
                currency = record.gross_revenue.currency
            elif record.gross_revenue.currency != currency:
                raise ValueError("Cannot sum revenue with mixed currencies")

            total_cents += record.gross_revenue.amount_cents

        if total_cents == 0:
            return None

        return Money(total_cents, currency)

    @staticmethod
    def calculate_recovered_revenue(
        attributions: list[Attribution],
        revenue_records: dict[str, RevenueRecord],
        jobs: dict[str, Job],  # keyed by job_id
    ) -> Optional[Money]:
        """Calculate total recovered (realized) revenue.

        Definition:
        - Sum of RevenueRecord.gross_revenue for APPROVED attributions
        - AND associated Job.status == COMPLETED
        - AND Job.completed_at is not None
        - Represents revenue that is confirmed as recovered
        - NOTE: This is the conservative measure of success

        Args:
            attributions: List of attribution objects
            revenue_records: Dict mapping revenue_record_id to RevenueRecord
            jobs: Dict mapping job_id to Job

        Returns:
            Total recovered revenue or None if no completed attributable jobs
        """
        from .value_objects import AttributionStatus

        approved = [
            a for a in attributions if a.status == AttributionStatus.APPROVED
        ]
        if not approved:
            return None

        total_cents = 0
        currency = None

        for attribution in approved:
            # Require both revenue record and completed job
            if not attribution.revenue_record_id or not attribution.job_id:
                continue

            record_id_str = str(attribution.revenue_record_id)
            job_id_str = str(attribution.job_id)

            if record_id_str not in revenue_records or job_id_str not in jobs:
                continue

            job = jobs[job_id_str]
            # Only count if job is actually completed
            if job.status != JobStatus.COMPLETED or job.completed_at is None:
                continue

            record = revenue_records[record_id_str]
            if currency is None:
                currency = record.gross_revenue.currency
            elif record.gross_revenue.currency != currency:
                raise ValueError("Cannot sum revenue with mixed currencies")

            total_cents += record.gross_revenue.amount_cents

        if total_cents == 0:
            return None

        return Money(total_cents, currency)

    # ========================================================================
    # PROFIT CALCULATIONS
    # ========================================================================

    @staticmethod
    def calculate_recovered_gross_profit(
        attributions: list[Attribution],
        revenue_records: dict[str, RevenueRecord],
        jobs: dict[str, Job],
    ) -> Optional[Money]:
        """Calculate total recovered gross profit.

        Definition:
        - Sum of RevenueRecord.gross_profit for recovered revenue
        - Requires RevenueRecord.gross_profit to be populated
        - If gross_profit is None for any record, that record is excluded
        - NOTE: Gross profit may not be available immediately

        Args:
            attributions: List of attribution objects
            revenue_records: Dict mapping revenue_record_id to RevenueRecord
            jobs: Dict mapping job_id to Job

        Returns:
            Total recovered gross profit or None if no profit data
        """
        from .value_objects import AttributionStatus

        approved = [
            a for a in attributions if a.status == AttributionStatus.APPROVED
        ]
        if not approved:
            return None

        total_cents = 0
        currency = None

        for attribution in approved:
            if not attribution.revenue_record_id or not attribution.job_id:
                continue

            record_id_str = str(attribution.revenue_record_id)
            job_id_str = str(attribution.job_id)

            if record_id_str not in revenue_records or job_id_str not in jobs:
                continue

            job = jobs[job_id_str]
            if job.status != JobStatus.COMPLETED or job.completed_at is None:
                continue

            record = revenue_records[record_id_str]
            # Only count if gross_profit is known
            if record.gross_profit is None:
                continue

            if currency is None:
                currency = record.gross_profit.currency
            elif record.gross_profit.currency != currency:
                raise ValueError("Cannot sum profit with mixed currencies")

            total_cents += record.gross_profit.amount_cents

        if total_cents == 0:
            return None

        return Money(total_cents, currency)

    # ========================================================================
    # MARGIN AND ROI
    # ========================================================================

    @staticmethod
    def calculate_contribution_margin(
        recovered_gross_profit: Optional[Money], system_cost: Money
    ) -> Optional[Money]:
        """Calculate contribution margin (profit - cost).

        Definition:
        - contribution_margin = recovered_gross_profit - system_cost
        - Represents net value created by recovery system
        - Negative margin allowed (system cost exceeded recovery profit)
        - NOTE: Profit must be known to calculate margin

        Args:
            recovered_gross_profit: Total recovered gross profit
            system_cost: System implementation and operational cost

        Returns:
            Contribution margin (can be negative) or None if profit is unknown
        """
        if recovered_gross_profit is None:
            return None

        if recovered_gross_profit.currency != system_cost.currency:
            raise ValueError(
                f"Cannot subtract {system_cost.currency} from "
                f"{recovered_gross_profit.currency}"
            )

        return recovered_gross_profit - system_cost

    @staticmethod
    def calculate_revenue_recovery_roi(
        recovered_gross_profit: Optional[Money], system_cost: Money
    ) -> Optional[float]:
        """Calculate Revenue Recovery ROI.

        Definition:
        ROI % = ((recovered_gross_profit - system_cost) / system_cost) * 100

        - Represents return on the system cost investment
        - Can be negative if recovery profit < system cost
        - NOTE: This is NOT recovery_rate or engagement_rate
        - NOTE: system_cost must be > 0

        Args:
            recovered_gross_profit: Total recovered gross profit
            system_cost: System cost (must be > 0)

        Returns:
            ROI as percentage or None if profit unknown or cost is zero

        Raises:
            ValueError: If system_cost is zero
        """
        if recovered_gross_profit is None:
            return None

        if system_cost.amount_cents == 0:
            return None  # Cannot divide by zero

        contribution_margin_cents = (
            recovered_gross_profit.amount_cents - system_cost.amount_cents
        )
        roi = (contribution_margin_cents / system_cost.amount_cents) * 100
        return roi
