"""Notification model — attention layer for OpportunityOS.

Notifications surface what deserves the user's attention.
They are informational only — they never execute external actions.

The Action Center is the canonical operational action system.
Notifications are the attention/reminder layer.

Notification types are deterministic and derived from existing database state.
Deduplication uses a deterministic key based on notification_type + source_type + source_id.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    """A notification alerting the user to something requiring attention."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)

    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(Text)

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_id: Mapped[int] = mapped_column(nullable=False)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# Indexes for efficient querying
Index("ix_notifications_notification_type", Notification.notification_type)
Index("ix_notifications_source", Notification.source_type, Notification.source_id)
Index("ix_notifications_read_at", Notification.read_at)
Index("ix_notifications_severity", Notification.severity)
Index("ix_notifications_created_at", Notification.created_at)

# Deduplication constraint: one active notification per type+source combination
# This uses a partial unique index — only enforce for non-dismissed notifications
# We handle this in the service layer for clarity.

# Notification types
NOTIFICATION_OVERDUE_ACTION = "OVERDUE_ACTION"
NOTIFICATION_FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
NOTIFICATION_DEADLINE_APPROACHING = "DEADLINE_APPROACHING"
NOTIFICATION_OUTREACH_PENDING_APPROVAL = "OUTREACH_PENDING_APPROVAL"
NOTIFICATION_OUTREACH_READY_TO_SEND = "OUTREACH_READY_TO_SEND"
NOTIFICATION_APPLICATION_UPDATE = "APPLICATION_UPDATE"
NOTIFICATION_HIGH_PRIORITY_OPPORTUNITY = "HIGH_PRIORITY_OPPORTUNITY"

ALL_NOTIFICATION_TYPES = [
    NOTIFICATION_OVERDUE_ACTION,
    NOTIFICATION_FOLLOW_UP_DUE,
    NOTIFICATION_DEADLINE_APPROACHING,
    NOTIFICATION_OUTREACH_PENDING_APPROVAL,
    NOTIFICATION_OUTREACH_READY_TO_SEND,
    NOTIFICATION_APPLICATION_UPDATE,
    NOTIFICATION_HIGH_PRIORITY_OPPORTUNITY,
]

# Severity levels
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"
