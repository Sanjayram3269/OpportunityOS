"""Follow-up service — CRUD and lifecycle management.

Uses the existing FollowUp model directly. No migration needed.

Lifecycle:
    PENDING → DUE → PENDING_APPROVAL → APPROVED → READY_TO_SEND
                                                ↘ CANCELLED

Terminal states: COMPLETED, CANCELLED

The service:
1. Creates follow-ups tied to leads/opportunities/messages
2. Manages state transitions with validation
3. Evaluates due state based on scheduled_for time
4. Never sends messages — actual delivery goes through outreach/send
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.followup import FollowUp
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

# ── Lifecycle states ─────────────────────────────────────────────────────

PENDING = "PENDING"
DUE = "DUE"
PENDING_APPROVAL = "PENDING_APPROVAL"
APPROVED = "APPROVED"
READY_TO_SEND = "READY_TO_SEND"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"

_VALID_TRANSITIONS: dict[str, set[str]] = {
    PENDING: {DUE, CANCELLED},
    DUE: {PENDING_APPROVAL, CANCELLED},
    PENDING_APPROVAL: {APPROVED, CANCELLED},
    APPROVED: {READY_TO_SEND, CANCELLED},
    READY_TO_SEND: {COMPLETED, CANCELLED},
    COMPLETED: set(),
    CANCELLED: set(),
}


class FollowUpStateError(Exception):
    """Raised when an invalid state transition is attempted."""


def can_transition(current: str, target: str) -> bool:
    """Check if a state transition is allowed."""
    return target in _VALID_TRANSITIONS.get(current, set())


# ── CRUD ─────────────────────────────────────────────────────────────────


def create_followup(
    db: Session,
    *,
    lead_id: int,
    opportunity_id: int | None = None,
    message_id: int | None = None,
    scheduled_for: datetime,
    reason: str | None = None,
) -> FollowUp:
    """Create a new follow-up.

    Validates that referenced entities exist.

    Raises:
        ValueError: If lead, opportunity, or message not found.
    """
    # Validate lead
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    # Validate opportunity if provided
    if opportunity_id is not None:
        opp = db.get(Opportunity, opportunity_id)
        if opp is None:
            raise ValueError(f"Opportunity {opportunity_id} not found")

    # Validate message if provided
    if message_id is not None:
        msg = db.get(Message, message_id)
        if msg is None:
            raise ValueError(f"Message {message_id} not found")

    # Reject naive datetime — must be timezone-aware
    if scheduled_for.tzinfo is None:
        raise ValueError(
            "scheduled_for must be timezone-aware. "
            "Use a timezone-aware datetime (e.g. 2026-01-01T12:00:00+00:00)."
        )

    followup = FollowUp(
        lead_id=lead_id,
        opportunity_id=opportunity_id,
        message_id=message_id,
        scheduled_for=scheduled_for,
        status=PENDING,
        reason=reason,
    )

    db.add(followup)
    db.commit()
    db.refresh(followup)

    logger.info("Follow-up created: id=%d, lead_id=%d", followup.id, lead_id)
    return followup


def get_followup(db: Session, followup_id: int) -> FollowUp | None:
    """Retrieve a follow-up by ID."""
    return db.get(FollowUp, followup_id)


def list_followups(
    db: Session,
    *,
    lead_id: int | None = None,
    opportunity_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[FollowUp]:
    """List follow-ups with optional filters."""
    stmt = select(FollowUp)
    if lead_id is not None:
        stmt = stmt.where(FollowUp.lead_id == lead_id)
    if opportunity_id is not None:
        stmt = stmt.where(FollowUp.opportunity_id == opportunity_id)
    if status is not None:
        stmt = stmt.where(FollowUp.status == status)
    stmt = stmt.order_by(FollowUp.scheduled_for.asc()).limit(limit)
    return list(db.scalars(stmt))


def update_followup(
    db: Session,
    followup: FollowUp,
    *,
    scheduled_for: datetime | None = None,
    reason: str | None = None,
) -> FollowUp:
    """Update a follow-up's content. Only allowed in PENDING or DUE state."""
    if followup.status not in (PENDING, DUE):
        raise FollowUpStateError(
            f"Cannot edit follow-up in {followup.status} state"
        )

    if scheduled_for is not None:
        if scheduled_for.tzinfo is None:
            raise ValueError(
                "scheduled_for must be timezone-aware. "
                "Use a timezone-aware datetime (e.g. 2026-01-01T12:00:00+00:00)."
            )
        followup.scheduled_for = scheduled_for

    if reason is not None:
        followup.reason = reason

    db.commit()
    db.refresh(followup)
    return followup


# ── State transitions ────────────────────────────────────────────────────


def transition_followup(
    db: Session,
    followup: FollowUp,
    target_status: str,
) -> FollowUp:
    """Transition a follow-up to a new status.

    Raises FollowUpStateError if the transition is not allowed.
    """
    if not can_transition(followup.status, target_status):
        raise FollowUpStateError(
            f"Cannot transition from {followup.status} to {target_status}"
        )

    followup.status = target_status

    if target_status == COMPLETED:
        followup.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(followup)
    return followup


def mark_due(db: Session, followup: FollowUp) -> FollowUp:
    """Mark a PENDING follow-up as DUE if its scheduled_for has passed.

    Raises FollowUpStateError if:
    - The follow-up is not in PENDING state
    - The scheduled_for time has not arrived yet
    """
    if followup.status != PENDING:
        raise FollowUpStateError(
            f"Cannot mark follow-up as due: current status is {followup.status}"
        )

    now = datetime.now(timezone.utc)
    scheduled = followup.scheduled_for

    if scheduled > now:
        raise FollowUpStateError(
            f"Follow-up is not yet due: scheduled for {scheduled.isoformat()}, "
            f"current time is {now.isoformat()}"
        )

    return transition_followup(db, followup, DUE)


def check_and_mark_due(db: Session, followup: FollowUp) -> FollowUp:
    """Check if a follow-up should be due and mark it if so.

    Returns the follow-up (possibly updated). Does not raise on
    non-due follow-ups — returns unchanged.
    """
    if followup.status != PENDING:
        return followup

    now = datetime.now(timezone.utc)
    scheduled = followup.scheduled_for

    if scheduled <= now:
        return mark_due(db, followup)

    return followup


def submit_followup(db: Session, followup: FollowUp) -> FollowUp:
    """Submit a DUE follow-up for approval (DUE → PENDING_APPROVAL)."""
    return transition_followup(db, followup, PENDING_APPROVAL)


def approve_followup(db: Session, followup: FollowUp) -> FollowUp:
    """Approve a follow-up (PENDING_APPROVAL → APPROVED)."""
    return transition_followup(db, followup, APPROVED)


def mark_followup_ready(db: Session, followup: FollowUp) -> FollowUp:
    """Mark an APPROVED follow-up as ready to send (APPROVED → READY_TO_SEND)."""
    return transition_followup(db, followup, READY_TO_SEND)


def complete_followup(db: Session, followup: FollowUp) -> FollowUp:
    """Mark a READY_TO_SEND follow-up as completed (READY_TO_SEND → COMPLETED)."""
    return transition_followup(db, followup, COMPLETED)


def cancel_followup(db: Session, followup: FollowUp) -> FollowUp:
    """Cancel a follow-up (any non-terminal state → CANCELLED)."""
    return transition_followup(db, followup, CANCELLED)
