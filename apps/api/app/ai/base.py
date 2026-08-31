"""AI provider abstraction and insight data model.

The AIProvider is an abstract base class that providers must implement.
AIInsight is the typed response model for AI-generated intelligence.

AI must be optional — when unavailable, AIInsight.available = False.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIInsight:
    """Structured AI-generated insight for an opportunity match.

    When AI is unavailable, ``available`` is False and all fields
    contain empty defaults. The deterministic score is NEVER
    modified by this layer.
    """

    available: bool = False
    provider: str = ""
    model: str = ""
    error: str | None = None

    match_explanation: str = ""
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    outreach_angles: list[str] = field(default_factory=list)
    application_advice: str = ""

    @classmethod
    def unavailable(cls, reason: str = "AI provider not configured") -> AIInsight:
        """Create an unavailable insight with a reason."""
        return cls(available=False, error=reason)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AIInsight:
        """Parse a dict (from AI JSON response) into an AIInsight.

        Only accepts known fields; unknown fields are silently ignored.
        """
        if not isinstance(data, dict):
            return cls(available=False, error="Invalid AI response format")

        def _list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(item) for item in val if item]
            if isinstance(val, str):
                return [val] if val else []
            return []

        return cls(
            available=True,
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            match_explanation=str(data.get("match_explanation", "")),
            strengths=_list(data.get("strengths")),
            gaps=_list(data.get("gaps")),
            recommendations=_list(data.get("recommendations")),
            outreach_angles=_list(data.get("outreach_angles")),
            application_advice=str(data.get("application_advice", "")),
        )


class AIProvider(ABC):
    """Abstract base class for AI insight providers.

    Subclasses implement ``generate_insight()`` which takes a structured
    context dict and returns a raw dict that will be parsed into AIInsight.

    The provider must:
    - Return a dict with the AIInsight fields
    - Handle network/HTTP errors internally (raise on unrecoverable failure)
    - Never fabricate data not present in the context
    """

    @abstractmethod
    async def generate_insight(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate an AI insight from the provided context.

        Args:
            context: Structured dict containing:
                - profile_summary (dict)
                - opportunity_summary (dict)
                - match_result (dict)
                - instructions (str)

        Returns:
            A dict matching AIInsight fields.

        Raises:
            AIPermissionError: If the provider is not configured.
            AITimeoutError: If the request times out.
            AIProviderError: On other provider failures.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier used."""


# ── Provider exceptions ──────────────────────────────────────────────────


class AIProviderError(Exception):
    """Base exception for AI provider failures."""


class AIPermissionError(AIProviderError):
    """Raised when the provider is not configured (missing API key, etc.)."""


class AITimeoutError(AIProviderError):
    """Raised when the provider request times out."""
