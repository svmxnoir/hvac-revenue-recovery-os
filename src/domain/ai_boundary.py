"""AI interpretation boundary and interface.

Defines how AI outputs integrate with deterministic business logic.

CRITICAL DESIGN PRINCIPLES:

1. DECOUPLING FROM LLM PROVIDER
   - No OpenAI, Anthropic, Gemini, LangChain imports
   - Abstract interface independent of implementation
   - Allows multiple providers or deterministic stubs

2. ADVISORY ONLY
   - AI output is interpretation, not authority
   - Business domain rules remain deterministic
   - AI cannot override domain decisions

3. NO BUSINESS LOGIC AUTHORITY
   - Cannot change opportunity state directly
   - Cannot authorize bookings
   - Cannot determine consent/compliance
   - Cannot determine availability
   - Cannot set pricing
   - Cannot create attribution
   - Cannot determine revenue

4. SEPARATION OF CONCERNS
   - IntentInterpreter interprets language
   - Domain services apply business rules
   - Controller/orchestrator layer bridges them
   - AI output is input to deterministic decisions
"""

from abc import ABC, abstractmethod
from .value_objects import IntentInterpretation


class IntentInterpreter(ABC):
    """Abstract interface for AI-based intent interpretation.

    FACT: AI is an interpretation component, not authority over business decisions.
    ASSUMPTION: AI output is advisory and must be validated by deterministic rules.
    DECISION: Decouple AI provider from domain logic via this interface.
    """

    @abstractmethod
    def interpret_customer_message(
        self, message: str, context: dict[str, str] | None = None
    ) -> IntentInterpretation:
        """Interpret customer message intent.

        Args:
            message: Customer message text
            context: Optional context dict (tenant_id, customer_id, etc.)

        Returns:
            IntentInterpretation with advisory classification

        Raises:
            InterpretationError: If interpretation fails

        CRITICAL GUARANTEES:
        - Output is advisory only
        - Domain logic must validate all fields
        - AI cannot invent availability
        - AI cannot invent pricing
        - AI cannot authorize bookings
        - AI cannot determine compliance status
        - Output must be deterministic and auditable
        """
        pass

    @abstractmethod
    def extract_service_category(
        self, message: str, context: dict[str, str] | None = None
    ) -> tuple[str, float]:
        """Extract service category from message.

        Args:
            message: Customer message text
            context: Optional context

        Returns:
            Tuple of (category, confidence) where confidence is 0-100

        Note:
        - Category must be validated against known service catalog
        - Confidence is advisory; do not use alone for decisions
        - Unknown categories must be explicitly labeled
        """
        pass


class InterpretationError(Exception):
    """Raised when AI interpretation cannot be performed."""

    pass


class StubIntentInterpreter(IntentInterpreter):
    """Deterministic stub implementation for testing without AI provider.

    Used in M0 for simulator and unit tests.
    Actual LLM integration comes in M1+.

    GUARANTEES:
    - Same input always produces same output
    - No external API calls
    - Results fully predictable for test scenarios
    - Can be parameterized for different test cases
    """

    def __init__(
        self,
        default_intent: str = "SERVICE_REQUEST",
        default_category: str = "HVAC_SERVICE",
        default_urgency: str = "MEDIUM",
        default_confidence: int = 75,
    ) -> None:
        """Initialize stub interpreter with default responses.

        Args:
            default_intent: Default intent classification
            default_category: Default service category
            default_urgency: Default urgency level
            default_confidence: Default confidence (0-100)
        """
        if not 0 <= default_confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

        self.default_intent = default_intent
        self.default_category = default_category
        self.default_urgency = default_urgency
        self.default_confidence = default_confidence
        # Allow test override via this dict
        self.overrides: dict[str, IntentInterpretation] = {}

    def set_override(
        self, message: str, interpretation: IntentInterpretation
    ) -> None:
        """Set a deterministic override for a specific message.

        Args:
            message: Message to override
            interpretation: Interpretation to return for this message
        """
        self.overrides[message] = interpretation

    def interpret_customer_message(
        self, message: str, context: dict[str, str] | None = None
    ) -> IntentInterpretation:
        """Interpret customer message (deterministic stub).

        Args:
            message: Customer message text
            context: Optional context (ignored in stub)

        Returns:
            Fixed IntentInterpretation for testing
        """
        # Check for override first
        if message in self.overrides:
            return self.overrides[message]

        # Return default interpretation
        return IntentInterpretation(
            intent=self.default_intent,
            service_category=self.default_category,
            urgency=self.default_urgency,
            customer_goal="Schedule service",
            confidence=self.default_confidence,
            unknown_fields={"stub": True, "message_length": len(message)},
        )

    def extract_service_category(
        self, message: str, context: dict[str, str] | None = None
    ) -> tuple[str, float]:
        """Extract service category (deterministic stub).

        Args:
            message: Customer message text
            context: Optional context (ignored in stub)

        Returns:
            Fixed category and confidence
        """
        # Stub always returns default category with default confidence
        return (self.default_category, self.default_confidence / 100.0)
