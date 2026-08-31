"""Email provider abstraction and delivery result model.

The EmailProvider is an abstract base class that providers must implement.
DeliveryResult is the typed response model for email delivery attempts.

Email sending is optional — when unconfigured, the system still works.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeliveryResult:
    """Structured result of an email delivery attempt."""

    success: bool = False
    provider: str = ""
    message_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, provider: str, message_id: str | None = None) -> DeliveryResult:
        return cls(success=True, provider=provider, message_id=message_id)

    @classmethod
    def fail(cls, provider: str, error: str) -> DeliveryResult:
        return cls(success=False, provider=provider, error=error)


class EmailProvider(ABC):
    """Abstract base class for email delivery providers.

    Subclasses implement ``send_email()`` which takes structured
    email data and returns a DeliveryResult.

    The provider must:
    - Handle network/SMTP errors internally
    - Return a DeliveryResult (never raise on delivery failure)
    - Never log or expose credentials
    """

    @abstractmethod
    def send_email(
        self,
        *,
        to_address: str,
        subject: str,
        body: str,
        from_address: str | None = None,
        from_name: str | None = None,
    ) -> DeliveryResult:
        """Send an email and return the delivery result.

        Args:
            to_address: Recipient email address.
            subject: Email subject line.
            body: Email body (plain text).
            from_address: Sender email (optional, from config if not provided).
            from_name: Sender display name (optional).

        Returns:
            A DeliveryResult with success status and details.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""


class EmailProviderError(Exception):
    """Base exception for email provider failures."""
