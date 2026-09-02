"""Application event model — tracks the timeline of application lifecycle changes.

Every status transition creates an event here. Events are never fabricated
for historical records created before this model existed.

Events are created transactionally alongside status changes in the
application service.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApplicationEvent(Base):
    """A single event in an application's lifecycle timeline."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)

    label: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    metadata_json: Mapped[str | None] = mapped_column(Text)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


Index("ix_application_events_application_id", ApplicationEvent.application_id)
Index("ix_application_events_event_type", ApplicationEvent.event_type)
Index("ix_application_events_occurred_at", ApplicationEvent.occurred_at)
Index(
    "ix_application_events_app_occurred",
    ApplicationEvent.application_id,
    ApplicationEvent.occurred_at,
)


# Event type constants
EVENT_APPLICATION_CREATED = "APPLICATION_CREATED"
EVENT_STATUS_CHANGED = "STATUS_CHANGED"
EVENT_APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
EVENT_ASSESSMENT = "ASSESSMENT"
EVENT_INTERVIEW = "INTERVIEW"
EVENT_FINAL_ROUND = "FINAL_ROUND"
EVENT_OFFER = "OFFER"
EVENT_ACCEPTED = "ACCEPTED"
EVENT_REJECTED = "REJECTED"
EVENT_WITHDRAWN = "WITHDRAWN"

# Map status → event type for automatic creation
STATUS_TO_EVENT: dict[str, str] = {
    "READY": EVENT_STATUS_CHANGED,
    "APPLIED": EVENT_APPLICATION_SUBMITTED,
    "ASSESSMENT": EVENT_ASSESSMENT,
    "INTERVIEW": EVENT_INTERVIEW,
    "FINAL_ROUND": EVENT_FINAL_ROUND,
    "OFFER": EVENT_OFFER,
    "ACCEPTED": EVENT_ACCEPTED,
    "REJECTED": EVENT_REJECTED,
    "WITHDRAWN": EVENT_WITHDRAWN,
}

# Friendly labels for events
EVENT_LABELS: dict[str, str] = {
    EVENT_APPLICATION_CREATED: "Application created",
    EVENT_STATUS_CHANGED: "Status updated",
    EVENT_APPLICATION_SUBMITTED: "Application submitted",
    EVENT_ASSESSMENT: "Assessment stage",
    EVENT_INTERVIEW: "Interview scheduled",
    EVENT_FINAL_ROUND: "Final round",
    EVENT_OFFER: "Offer received",
    EVENT_ACCEPTED: "Offer accepted",
    EVENT_REJECTED: "Application rejected",
    EVENT_WITHDRAWN: "Application withdrawn",
}
