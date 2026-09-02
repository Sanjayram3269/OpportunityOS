"""Application lifecycle service — state machine and application tracking.

Manages the full lifecycle of a user's engagement with an opportunity:

NOT_APPLIED → READY → APPLIED → ASSESSMENT/INTERVIEW → FINAL_ROUND → OFFER → ACCEPTED

Any active state → REJECTED / WITHDRAWN (terminal states)

Safety rules:
- All transitions require explicit user actions (POST endpoints)
- Automation NEVER submits applications automatically
- State transitions are deterministic and validated
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.application import (
    APPLICATION_TRANSITIONS,
    TERMINAL_STATUSES,
    Application,
    can_transition,
)
from app.models.application_event import (
    EVENT_APPLICATION_CREATED,
    EVENT_LABELS,
    STATUS_TO_EVENT,
    ApplicationEvent,
)
from app.models.company import Company
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)


def create_application(
    db: Session,
    *,
    opportunity_id: int,
    lead_id: int | None = None,
    application_url: str | None = None,
    notes: str | None = None,
) -> Application:
    """Create a new application in NOT_APPLIED status.

    The opportunity must exist. One application per opportunity is enforced.
    """
    opp = db.get(Opportunity, opportunity_id)
    if opp is None:
        raise ValueError(f"Opportunity {opportunity_id} not found")

    existing = (
        db.query(Application)
        .filter(Application.opportunity_id == opportunity_id)
        .first()
    )
    if existing is not None:
        raise ValueError(
            f"Application already exists for opportunity {opportunity_id}"
        )

    now = datetime.now(timezone.utc)
    app = Application(
        opportunity_id=opportunity_id,
        lead_id=lead_id,
        status="NOT_APPLIED",
        application_url=application_url,
        notes=notes,
        created_at=now,
        updated_at=now,
    )
    db.add(app)
    db.flush()

    # Create timeline event
    event = ApplicationEvent(
        application_id=app.id,
        event_type=EVENT_APPLICATION_CREATED,
        from_status=None,
        to_status="NOT_APPLIED",
        label=EVENT_LABELS[EVENT_APPLICATION_CREATED],
        occurred_at=now,
    )
    db.add(event)
    db.flush()

    return app


def transition_application(
    db: Session,
    application_id: int,
    new_status: str,
    *,
    notes: str | None = None,
    rejection_reason: str | None = None,
    application_url: str | None = None,
) -> Application:
    """Transition an application to a new status.

    Returns the updated application or raises ValueError on invalid transition.
    """
    app = db.get(Application, application_id)
    if app is None:
        raise ValueError(f"Application {application_id} not found")

    if not can_transition(app.status, new_status):
        raise ValueError(
            f"Invalid transition: {app.status} → {new_status}. "
            f"Allowed: {APPLICATION_TRANSITIONS.get(app.status, [])}"
        )

    now = datetime.now(timezone.utc)
    old_status = app.status
    app.status = new_status
    app.last_status_change_at = now
    app.updated_at = now

    if notes is not None:
        app.notes = notes
    if rejection_reason is not None:
        app.rejection_reason = rejection_reason
    if application_url is not None:
        app.application_url = application_url

    # Track when the application was first submitted
    if new_status == "APPLIED" and app.applied_at is None:
        app.applied_at = now

    db.flush()

    # Create timeline event
    event_type = STATUS_TO_EVENT.get(new_status, "STATUS_CHANGED")
    label = EVENT_LABELS.get(event_type, f"Status changed to {new_status}")
    event = ApplicationEvent(
        application_id=app.id,
        event_type=event_type,
        from_status=old_status,
        to_status=new_status,
        label=label,
        occurred_at=now,
    )
    db.add(event)
    db.flush()

    logger.info(
        "Application %d transitioned: %s → %s", application_id, old_status, new_status
    )
    return app


def get_application(db: Session, application_id: int) -> Application | None:
    """Get a single application by ID."""
    return db.get(Application, application_id)


def list_applications(
    db: Session,
    *,
    status: str | None = None,
    opportunity_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Application]:
    """List applications with optional filters."""
    query = db.query(Application)
    if status is not None:
        query = query.filter(Application.status == status)
    if opportunity_id is not None:
        query = query.filter(Application.opportunity_id == opportunity_id)
    return query.order_by(Application.created_at.desc()).offset(offset).limit(limit).all()


def count_applications_by_status(db: Session) -> dict[str, int]:
    """Count applications grouped by status."""
    from sqlalchemy import func

    results = (
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    return {status: count for status, count in results}


def get_application_with_context(db: Session, application_id: int) -> dict | None:
    """Get application with opportunity and company context."""
    app = db.get(Application, application_id)
    if app is None:
        return None

    opp = db.get(Opportunity, app.opportunity_id)
    company = db.get(Company, opp.company_id) if opp else None

    return {
        "application": app,
        "opportunity": opp,
        "company": company,
    }
