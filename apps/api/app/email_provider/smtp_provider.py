"""SMTP email provider — uses Python's built-in smtplib.

Works with any SMTP server:
  - Gmail (smtp.gmail.com:587)
  - Outlook (smtp.office365.com:587)
  - Custom SMTP servers

No external dependencies required.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.email_provider.base import EmailProvider, DeliveryResult

logger = logging.getLogger(__name__)


class SMTPEmailProvider(EmailProvider):
    """Email provider using SMTP directly.

    Configuration:
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port (default 587 for STARTTLS)
        smtp_username: SMTP authentication username
        smtp_password: SMTP authentication password
        smtp_use_tls: Whether to use STARTTLS (default True)
        from_address: Default sender email address
        from_name: Default sender display name
        timeout: Connection timeout in seconds
    """

    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        smtp_use_tls: bool = True,
        from_address: str | None = None,
        from_name: str | None = None,
        timeout: int = 30,
    ) -> None:
        self._host = smtp_host
        self._port = smtp_port
        self._username = smtp_username
        self._password = smtp_password
        self._use_tls = smtp_use_tls
        self._from_address = from_address
        self._from_name = from_name
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "smtp"

    def send_email(
        self,
        *,
        to_address: str,
        subject: str,
        body: str,
        from_address: str | None = None,
        from_name: str | None = None,
    ) -> DeliveryResult:
        """Send an email via SMTP."""
        sender = from_address or self._from_address
        sender_name = from_name or self._from_name

        if not sender:
            return DeliveryResult.fail(
                self.provider_name,
                "No sender email address configured",
            )

        if not to_address:
            return DeliveryResult.fail(
                self.provider_name,
                "No recipient email address provided",
            )

        try:
            # Build the email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{sender_name} <{sender}>" if sender_name else sender
            msg["To"] = to_address

            # Attach the body as plain text
            msg.attach(MIMEText(body, "plain"))

            # Connect and send
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as server:
                if self._use_tls:
                    server.starttls()

                if self._username and self._password:
                    server.login(self._username, self._password)

                server.sendmail(sender, [to_address], msg.as_string())

            logger.info("Email sent to %s via %s", to_address, self.provider_name)

            # Generate a message ID (SMTP doesn't always return one)
            import uuid
            local_id = str(uuid.uuid4())

            return DeliveryResult.ok(
                provider=self.provider_name,
                message_id=local_id,
            )

        except smtplib.SMTPAuthenticationError as exc:
            error_msg = f"SMTP authentication failed: {exc}"
            logger.error(error_msg)
            return DeliveryResult.fail(self.provider_name, error_msg)

        except smtplib.SMTPRecipientsRefused as exc:
            error_msg = f"Recipient refused: {exc}"
            logger.error(error_msg)
            return DeliveryResult.fail(self.provider_name, error_msg)

        except smtplib.SMTPException as exc:
            error_msg = f"SMTP error: {exc}"
            logger.error(error_msg)
            return DeliveryResult.fail(self.provider_name, error_msg)

        except Exception as exc:
            # TimeoutError is a subclass of Exception; handle it here
            if isinstance(exc, TimeoutError):
                error_msg = f"SMTP connection timed out ({self._timeout}s)"
                logger.error(error_msg)
                return DeliveryResult.fail(self.provider_name, error_msg)
            error_msg = f"Unexpected error: {type(exc).__name__}: {exc}"
            logger.error(error_msg)
            return DeliveryResult.fail(self.provider_name, error_msg)
            error_msg = f"Unexpected error: {type(exc).__name__}: {exc}"
            logger.error(error_msg)
            return DeliveryResult.fail(self.provider_name, error_msg)
