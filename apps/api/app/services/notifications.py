"""Notification service — deterministic generation and management of attention notifications.

This is the attention layer. It answers: "What deserves the user's attention now?"

The Action Center is the canonical operational action system.
Notifications are the attention/reminder layer.

Key properties:
- Deterministic: same input → same notifications
- Idempotent: safe to run repeatedly, no duplicates
- Database-backed: PostgreSQL is source of truth
- No external side effects: never sends emails, never applies, never approves
- Bounded: limits notification count, prevents notification spam

Notification generation derives from existing database state only.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.application import Action, Application
from app.models.followup import FollowUp
from app.models.message import Message
from app.models.notification import (
    NOTIFICATION_APPLICATION_UPDATE,
    NOTIFICATION_DEADLINE_APPROACHING,
    NOTIFICATION_FOLLOW_UP_DUE,
    NOTIFICATION_HIGH_PRIORITY_OPPORTUNITY,
    NOTIFICATION_OUTREACH_PENDING_APPROVAL,
    NOTIFICATION_OUTREACH_READY_TO_SEND,
    NOTIFICATION_OVERDUE_ACTION,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    Notification,
)
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

# Maximum notifications to generate per sync to prevent spam
_MAX_NOTIFICATIONS_PER_TYPE = 20

# Deadline windows
_DEADLINE_APPROACHING_DAYS = 7


def _make_dedup_key(
    notification_type: str,
    source_type: str,
    source_id: int,
) -> str:
    """Create a deterministic deduplication key."""
    return f"{notification_type}:{source_type}:{source_id}"


def _get_existing_notification(
    db: Session,
    dedup_key: str,
) -> Notification | None:
    """Find an existing non-dismissed notification with the given dedup key."""
    ntype, stype, sid = dedup_key.split(":", 2)
    return (
        db.query(Notification)
        .filter(
            Notification.notification_type == ntype,
            Notification.source_type == stype,
            Notification.source_id == int(sid),
            Notification.dismissed_at.is_(None),
        )
        .first()
    )


def _create_notification(
    db: Session,
    *,
    notification_type: str,
    title: str,
    message: str | None,
    severity: str,
    source_type: str,
    source_id: int,
    due_at: datetime | None = None,
    now: datetime | None = None,
) -> Notification | None:
    """Create a notification if it doesn't already exist (idempotent).

    Returns the new Notification or None if a duplicate already exists.
    """
    dedup_key = _make_dedup_key(notification_type, source_type, source_id)
    existing = _get_existing_notification(db, dedup_key)
    if existing is not None:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    notification = Notification(
        notification_type=notification_type,
        title=title,
        message=message,
        severity=severity,
        source_type=source_type,
        source_id=source_id,
        due_at=due_at,
        created_at=now,
    )
    db.add(notification)
    return notification


# ── Generation functions ─────────────────────────────────────────────────


def _generate_overdue_action_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for overdue actions."""
    count = 0
    overdue_actions = (
        db.query(Action)
        .filter(
            Action.status.in_(["OPEN", "IN_PROGRESS"]),
            Action.due_at.isnot(None),
            Action.due_at < now,
        )
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for action in overdue_actions:
        result = _create_notification(
            db,
            notification_type=NOTIFICATION_OVERDUE_ACTION,
            title=f"Overdue: {action.title}",
            message=f"Action '{action.title}' was due {action.due_at.strftime('%b %d, %Y')}.",
            severity=SEVERITY_CRITICAL,
            source_type="action",
            source_id=action.id,
            due_at=action.due_at,
            now=now,
        )
        if result is not None:
            count += 1

    return count


def _generate_followup_due_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for due follow-ups."""
    count = 0
    due_followups = (
        db.query(FollowUp)
        .filter(FollowUp.status == "DUE")
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for fu in due_followups:
        result = _create_notification(
            db,
            notification_type=NOTIFICATION_FOLLOW_UP_DUE,
            title=f"Follow-up due (ID: {fu.id})",
            message=f"Follow-up scheduled for {fu.scheduled_for.strftime('%b %d, %Y')} is now due.",
            severity=SEVERITY_HIGH,
            source_type="followup",
            source_id=fu.id,
            due_at=fu.scheduled_for,
            now=now,
        )
        if result is not None:
            count += 1

    return count


def _generate_deadline_approaching_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for opportunities with approaching deadlines.

    Only generates for opportunities not yet fully applied (terminal or deep in pipeline).
    Does NOT use created_at as a deadline.
    """
    count = 0
    window_end = now + timedelta(days=_DEADLINE_APPROACHING_DAYS)

    opportunities = (
        db.query(Opportunity)
        .filter(
            Opportunity.deadline.isnot(None),
            Opportunity.deadline > now,  # not overdue
            Opportunity.deadline <= window_end,
        )
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for opp in opportunities:
        # Check if application is already in a deep pipeline state
        app = (
            db.query(Application)
            .filter(Application.opportunity_id == opp.id)
            .first()
        )
        if app and app.status in (
            "INTERVIEW", "FINAL_ROUND", "OFFER", "ACCEPTED",
            "REJECTED", "WITHDRAWN",
        ):
            continue

        days_until = (opp.deadline - now).days
        severity = SEVERITY_HIGH if days_until <= 3 else SEVERITY_MEDIUM

        result = _create_notification(
            db,
            notification_type=NOTIFICATION_DEADLINE_APPROACHING,
            title=f"Deadline in {days_until}d: {opp.title}",
            message=f"Deadline is {opp.deadline.strftime('%b %d, %Y')}.",
            severity=severity,
            source_type="opportunity",
            source_id=opp.id,
            due_at=opp.deadline,
            now=now,
        )
        if result is not None:
            count += 1

    return count


def _generate_outreach_pending_approval_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for outreach messages pending approval."""
    count = 0
    messages = (
        db.query(Message)
        .filter(Message.status == "PENDING_APPROVAL")
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for msg in messages:
        result = _create_notification(
            db,
            notification_type=NOTIFICATION_OUTREACH_PENDING_APPROVAL,
            title=f"Outreach pending approval (ID: {msg.id})",
            message=f"Message '{msg.subject or msg.body[:50]}' is awaiting approval.",
            severity=SEVERITY_MEDIUM,
            source_type="message",
            source_id=msg.id,
            now=now,
        )
        if result is not None:
            count += 1

    return count


def _generate_outreach_ready_to_send_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for outreach messages ready to send."""
    count = 0
    messages = (
        db.query(Message)
        .filter(Message.status == "READY_TO_SEND")
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for msg in messages:
        result = _create_notification(
            db,
            notification_type=NOTIFICATION_OUTREACH_READY_TO_SEND,
            title=f"Outreach ready to send (ID: {msg.id})",
            message=f"Approved message '{msg.subject or msg.body[:50]}' is ready to send.",
            severity=SEVERITY_HIGH,
            source_type="message",
            source_id=msg.id,
            now=now,
        )
        if result is not None:
            count += 1

    return count


def _generate_application_update_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for recent application status changes.

    Only notifies for significant status changes, not routine transitions.
    """
    from app.models.application_event import ApplicationEvent

    count = 0
    # Look for significant recent events (last 24h)
    cutoff = now - timedelta(hours=24)
    significant_events = (
        db.query(ApplicationEvent)
        .filter(
            ApplicationEvent.event_type.in_([
                "INTERVIEW",
                "FINAL_ROUND",
                "OFFER",
                "REJECTED",
                "WITHDRAWN",
            ]),
            ApplicationEvent.occurred_at >= cutoff,
        )
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for event in significant_events:
        result = _create_notification(
            db,
            notification_type=NOTIFICATION_APPLICATION_UPDATE,
            title=f"Application {event.to_status.lower().replace('_', ' ')}",
            message=event.label,
            severity=(
                SEVERITY_HIGH
                if event.event_type in ("OFFER", "REJECTED")
                else SEVERITY_MEDIUM
            ),
            source_type="application_event",
            source_id=event.id,
            now=now,
        )
        if result is not None:
            count += 1

    return count


def _generate_high_priority_opportunity_notifications(
    db: Session, now: datetime
) -> int:
    """Generate notifications for high-priority opportunities not yet applied to."""
    count = 0
    high_priority_opps = (
        db.query(Opportunity)
        .filter(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 90,
            Opportunity.priority == "HIGH",
        )
        .limit(_MAX_NOTIFICATIONS_PER_TYPE)
        .all()
    )

    for opp in high_priority_opps:
        # Check if already applied
        existing_app = (
            db.query(Application)
            .filter(Application.opportunity_id == opp.id)
            .first()
        )
        if existing_app is not None:
            continue

        result = _create_notification(
            db,
            notification_type=NOTIFICATION_HIGH_PRIORITY_OPPORTUNITY,
            title=f"High priority: {opp.title}",
            message=f"Match score {opp.match_score}/100. Not yet applied.",
            severity=SEVERITY_MEDIUM,
            source_type="opportunity",
            source_id=opp.id,
            due_at=opp.deadline,
            now=now,
        )
        if result is not None:
            count += 1

    return count


# ── Public API ───────────────────────────────────────────────────────────


def sync_notifications(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict:
    """Synchronize notifications from current system state.

    This is the main generation entry point. It:
    1. Inspects current operational state
    2. Generates missing notifications (idempotent)
    3. Does NOT create duplicates for existing unread notifications
    4. Returns a summary of what was created

    Safety: This endpoint creates attention records ONLY.
    It does NOT send emails, does NOT apply to jobs, does NOT execute actions.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    created = 0

    created += _generate_overdue_action_notifications(db, now)
    created += _generate_followup_due_notifications(db, now)
    created += _generate_deadline_approaching_notifications(db, now)
    created += _generate_outreach_pending_approval_notifications(db, now)
    created += _generate_outreach_ready_to_send_notifications(db, now)
    created += _generate_application_update_notifications(db, now)
    created += _generate_high_priority_opportunity_notifications(db, now)

    db.flush()

    return {
        "created": created,
        "timestamp": now.isoformat(),
    }


def list_notifications(
    db: Session,
    *,
    unread_only: bool = False,
    notification_type: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    """List notifications with optional filters.

    Ordering: unread first, then by severity (CRITICAL > HIGH > MEDIUM > LOW),
    then by created_at descending (newest first).
    """
    query = db.query(Notification).filter(
        Notification.dismissed_at.is_(None),
    )

    if unread_only:
        query = query.filter(Notification.read_at.is_(None))

    if notification_type is not None:
        query = query.filter(Notification.notification_type == notification_type)

    if severity is not None:
        query = query.filter(Notification.severity == severity)

    # Custom ordering: unread first, then by severity, then by created_at desc
    severity_order = case(
        (Notification.severity == SEVERITY_CRITICAL, 0),
        (Notification.severity == SEVERITY_HIGH, 1),
        (Notification.severity == SEVERITY_MEDIUM, 2),
        (Notification.severity == SEVERITY_LOW, 3),
        else_=4,
    )

    return (
        query.order_by(
            Notification.read_at.desc().nullsfirst(),
            severity_order.asc(),
            Notification.created_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_unread_count(db: Session) -> int:
    """Get the count of unread, non-dismissed notifications."""
    return (
        db.query(func.count(Notification.id))
        .filter(
            Notification.read_at.is_(None),
            Notification.dismissed_at.is_(None),
        )
        .scalar()
        or 0
    )


def mark_read(db: Session, notification_id: int) -> Notification:
    """Mark a notification as read."""
    notification = db.get(Notification, notification_id)
    if notification is None:
        raise ValueError(f"Notification {notification_id} not found")
    if notification.read_at is not None:
        return notification  # Already read
    notification.read_at = datetime.now(timezone.utc)
    db.flush()
    return notification


def mark_all_read(db: Session) -> int:
    """Mark all unread notifications as read. Returns count of updated."""
    now = datetime.now(timezone.utc)
    count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.read_at.is_(None),
            Notification.dismissed_at.is_(None),
        )
        .scalar()
        or 0
    )
    if count > 0:
        db.query(Notification).filter(
            Notification.read_at.is_(None),
            Notification.dismissed_at.is_(None),
        ).update({"read_at": now})
        db.flush()
    return count
