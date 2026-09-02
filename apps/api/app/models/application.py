"""Application and Action models — lifecycle tracking and action center.

Application tracks the user's engagement with a specific opportunity.
Action tracks concrete things the user should do.

Automation MAY generate actions.
Automation MUST NEVER submit applications automatically.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Application(Base):
    """Tracks a user's application lifecycle for an opportunity."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)

    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )

    lead_id: Mapped[int | None] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="NOT_APPLIED",
    )

    application_url: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status_change_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


Index("ix_applications_opportunity_id", Application.opportunity_id)
Index("ix_applications_status", Application.status)
Index("ix_applications_lead_id", Application.lead_id)


# ── Valid application status transitions ──────────────────────────────

APPLICATION_TRANSITIONS: dict[str, list[str]] = {
    "NOT_APPLIED": ["READY"],
    "READY": ["APPLIED", "REJECTED", "WITHDRAWN"],
    "APPLIED": ["ASSESSMENT", "INTERVIEW", "REJECTED", "WITHDRAWN"],
    "ASSESSMENT": ["INTERVIEW", "FINAL_ROUND", "REJECTED", "WITHDRAWN"],
    "INTERVIEW": ["FINAL_ROUND", "OFFER", "REJECTED", "WITHDRAWN"],
    "FINAL_ROUND": ["OFFER", "REJECTED", "WITHDRAWN"],
    "OFFER": ["ACCEPTED", "REJECTED", "WITHDRAWN"],
}

TERMINAL_STATUSES = {"ACCEPTED", "REJECTED", "WITHDRAWN"}


def can_transition(current: str, target: str) -> bool:
    """Check if a status transition is valid."""
    if current in TERMINAL_STATUSES:
        return False
    allowed = APPLICATION_TRANSITIONS.get(current, [])
    return target in allowed


def transition_to_status(current: str, target: str) -> str:
    """Transition to a new status or raise ValueError."""
    if not can_transition(current, target):
        raise ValueError(
            f"Invalid transition: {current} → {target}. "
            f"Allowed: {APPLICATION_TRANSITIONS.get(current, [])}"
        )
    return target


class Action(Base):
    """A concrete action item for the user to take."""

    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)

    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="P3",
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    entity_id: Mapped[int] = mapped_column(nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
    )

    source: Mapped[str | None] = mapped_column(String(100))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


Index("ix_actions_action_type", Action.action_type)
Index("ix_actions_status", Action.status)
Index("ix_actions_priority", Action.priority)
Index("ix_actions_entity_type_id", Action.entity_type, Action.entity_id)
Index("ix_actions_due_at", Action.due_at)

# Action statuses
ACTION_OPEN = "OPEN"
ACTION_IN_PROGRESS = "IN_PROGRESS"
ACTION_COMPLETED = "COMPLETED"
ACTION_DISMISSED = "DISMISSED"
ACTION_EXPIRED = "EXPIRED"

TERMINAL_ACTION_STATUSES = {ACTION_COMPLETED, ACTION_DISMISSED, ACTION_EXPIRED}

ACTION_TRANSITIONS: dict[str, list[str]] = {
    ACTION_OPEN: [ACTION_IN_PROGRESS, ACTION_COMPLETED, ACTION_DISMISSED],
    ACTION_IN_PROGRESS: [ACTION_COMPLETED, ACTION_DISMISSED],
}
