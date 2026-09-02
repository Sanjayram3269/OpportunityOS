"""Action Center service — triage, priority, deadline intelligence, and action generation.

This is the core intelligence that answers: "What should I do next?"

The action center:
1. Evaluates every opportunity through a priority engine
2. Generates concrete action items from system state
3. Prevents duplicate actions (idempotent)
4. Respects safety boundaries (no auto-apply, no auto-send)
5. Connects discovery → matching → planning → actionable queue

Safety rules:
- Automation MAY generate action items
- Automation MUST NEVER execute actions (apply, send, approve)
- All outbound actions require explicit human decision
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.application import (
    ACTION_COMPLETED,
    ACTION_DISMISSED,
    ACTION_EXPIRED,
    ACTION_IN_PROGRESS,
    ACTION_OPEN,
    TERMINAL_ACTION_STATUSES,
    Action,
    Application,
)
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.planning import (
    HORIZON_NOW,
    HORIZON_SUMMER_2027,
    HORIZON_UNKNOWN,
    HORIZON_UPCOMING,
    classify_horizon,
)

logger = logging.getLogger(__name__)

# ── Action types ──────────────────────────────────────────────────────

ACTION_REVIEW_OPPORTUNITY = "REVIEW_OPPORTUNITY"
ACTION_APPLY = "APPLY"
ACTION_APPROVE_OUTREACH = "APPROVE_OUTREACH"
ACTION_SEND_OUTREACH = "SEND_OUTREACH"
ACTION_FOLLOW_UP = "FOLLOW_UP"
ACTION_INTERVIEW = "INTERVIEW"
ACTION_ASSESSMENT = "ASSESSMENT"
ACTION_UPDATE_APPLICATION = "UPDATE_APPLICATION"
ACTION_REVIEW_DEADLINE = "REVIEW_DEADLINE"
ACTION_RESEARCH_COMPANY = "RESEARCH_COMPANY"

ALL_ACTION_TYPES = [
    ACTION_REVIEW_OPPORTUNITY,
    ACTION_APPLY,
    ACTION_APPROVE_OUTREACH,
    ACTION_SEND_OUTREACH,
    ACTION_FOLLOW_UP,
    ACTION_INTERVIEW,
    ACTION_ASSESSMENT,
    ACTION_UPDATE_APPLICATION,
    ACTION_REVIEW_DEADLINE,
    ACTION_RESEARCH_COMPANY,
]

# ── Priority levels ───────────────────────────────────────────────────

PRIORITY_P0 = "P0"
PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"
PRIORITY_P3 = "P3"


# ── Deadline Intelligence ─────────────────────────────────────────────

def classify_deadline_bucket(deadline: datetime | None, now: datetime | None = None) -> str:
    """Classify a deadline into a deterministic bucket.

    Returns one of: OVERDUE, TODAY, WITHIN_3_DAYS, WITHIN_7_DAYS,
    WITHIN_14_DAYS, WITHIN_30_DAYS, FUTURE, NO_DEADLINE
    """
    if deadline is None:
        return "NO_DEADLINE"

    if now is None:
        now = datetime.now(timezone.utc)

    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    days_until = (deadline - now).days

    if days_until < 0:
        return "OVERDUE"
    elif days_until == 0:
        return "TODAY"
    elif days_until <= 3:
        return "WITHIN_3_DAYS"
    elif days_until <= 7:
        return "WITHIN_7_DAYS"
    elif days_until <= 14:
        return "WITHIN_14_DAYS"
    elif days_until <= 30:
        return "WITHIN_30_DAYS"
    else:
        return "FUTURE"


# ── Priority Engine ───────────────────────────────────────────────────

def calculate_action_priority(
    *,
    match_score: int | None,
    planning_horizon: str,
    deadline_bucket: str,
    application_status: str,
    now: datetime | None = None,
) -> str:
    """Calculate a deterministic action priority (P0-P3).

    The priority engine answers: "What deserves attention first?"

    P0: deadline imminent + high match + not applied
    P1: Summer 2027 + high match, OR deadline approaching + moderate match
    P2: strong match + future deadline
    P3: lower match or no urgent action needed

    Unknown information is not treated as urgent merely because it's missing.
    """
    is_high_match = match_score is not None and match_score >= 80
    is_moderate_match = match_score is not None and match_score >= 60
    is_not_applied = application_status in ("NOT_APPLIED", "READY")

    # P0: imminent deadline + high match + not yet applied
    if deadline_bucket in ("OVERDUE", "TODAY", "WITHIN_3_DAYS"):
        if is_high_match and is_not_applied:
            return PRIORITY_P0
        if is_moderate_match and is_not_applied and deadline_bucket in ("OVERDUE", "TODAY"):
            return PRIORITY_P0

    # P1: Summer 2027 + high match + not applied, or deadline within 7 days + moderate match
    if planning_horizon == HORIZON_SUMMER_2027:
        if is_high_match and is_not_applied:
            return PRIORITY_P1
        if is_moderate_match and is_not_applied:
            return PRIORITY_P1

    if deadline_bucket in ("WITHIN_7_DAYS",):
        if is_moderate_match and is_not_applied:
            return PRIORITY_P1

    # P2: strong match + future deadline, or upcoming deadline
    if is_high_match and deadline_bucket in ("WITHIN_14_DAYS", "WITHIN_30_DAYS", "FUTURE"):
        return PRIORITY_P2

    if is_moderate_match and deadline_bucket in ("WITHIN_7_DAYS", "WITHIN_14_DAYS"):
        return PRIORITY_P2

    if deadline_bucket == "WITHIN_14_DAYS" and is_not_applied:
        return PRIORITY_P2

    # P3: everything else
    return PRIORITY_P3


# ── Triage Service ────────────────────────────────────────────────────

def triage_opportunity(
    db: Session,
    opportunity: Opportunity,
    *,
    now: datetime | None = None,
) -> dict:
    """Produce a deterministic triage assessment for a single opportunity.

    Returns:
        A dict with opportunity_id, match_score, planning_horizon,
        deadline_bucket, application_status, recommended_action,
        priority, and explanation.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Planning horizon
    horizon = classify_horizon(opportunity.deadline, now)

    # Deadline bucket
    deadline_bucket = classify_deadline_bucket(opportunity.deadline, now)

    # Application status
    application = (
        db.query(Application)
        .filter(Application.opportunity_id == opportunity.id)
        .first()
    )
    app_status = application.status if application else "NOT_APPLIED"

    # Priority
    priority = calculate_action_priority(
        match_score=opportunity.match_score,
        planning_horizon=horizon,
        deadline_bucket=deadline_bucket,
        application_status=app_status,
        now=now,
    )

    # Recommended action
    recommended_action = _recommend_action(
        application_status=app_status,
        deadline_bucket=deadline_bucket,
        horizon=horizon,
        match_score=opportunity.match_score,
    )

    # Build explanation
    explanation = _build_explanation(
        match_score=opportunity.match_score,
        horizon=horizon,
        deadline_bucket=deadline_bucket,
        app_status=app_status,
        recommended_action=recommended_action,
    )

    return {
        "opportunity_id": opportunity.id,
        "match_score": opportunity.match_score,
        "planning_horizon": horizon,
        "deadline_bucket": deadline_bucket,
        "application_status": app_status,
        "recommended_action": recommended_action,
        "priority": priority,
        "explanation": explanation,
    }


def _recommend_action(
    *,
    application_status: str,
    deadline_bucket: str,
    horizon: str,
    match_score: int | None,
) -> str:
    """Determine the recommended next action for an opportunity."""
    if application_status in ("ACCEPTED", "REJECTED", "WITHDRAWN"):
        return "NONE"

    if application_status == "NOT_APPLIED":
        if match_score is not None and match_score >= 60:
            return ACTION_APPLY
        return ACTION_REVIEW_OPPORTUNITY

    if application_status == "READY":
        return ACTION_APPLY

    if application_status in ("APPLIED", "ASSESSMENT"):
        if deadline_bucket in ("OVERDUE", "TODAY", "WITHIN_3_DAYS"):
            return ACTION_UPDATE_APPLICATION
        return ACTION_UPDATE_APPLICATION

    if application_status in ("INTERVIEW", "FINAL_ROUND"):
        return ACTION_INTERVIEW

    if application_status == "OFFER":
        return ACTION_UPDATE_APPLICATION

    return ACTION_UPDATE_APPLICATION


def _build_explanation(
    *,
    match_score: int | None,
    horizon: str,
    deadline_bucket: str,
    app_status: str,
    recommended_action: str,
) -> str:
    """Build a deterministic explanation string."""
    parts = []

    if match_score is not None:
        if match_score >= 80:
            parts.append(f"Excellent match ({match_score}/100)")
        elif match_score >= 60:
            parts.append(f"Good match ({match_score}/100)")
        else:
            parts.append(f"Lower match ({match_score}/100)")
    else:
        parts.append("Match score not yet calculated")

    if horizon == HORIZON_SUMMER_2027:
        parts.append("Summer 2027 opportunity")
    elif horizon == HORIZON_NOW:
        parts.append("Deadline is imminent")
    elif horizon == HORIZON_UPCOMING:
        parts.append("Upcoming deadline")
    elif horizon == HORIZON_UNKNOWN:
        parts.append("No known deadline")

    if deadline_bucket == "OVERDUE":
        parts.append("OVERDUE")
    elif deadline_bucket == "TODAY":
        parts.append("Due today")

    if app_status == "NOT_APPLIED":
        parts.append("not yet applied")
    elif app_status in ("ACCEPTED", "REJECTED", "WITHDRAWN"):
        parts.append(f"application {app_status.lower()}")

    if recommended_action != "NONE":
        parts.append(f"→ {recommended_action.replace('_', ' ').title()}")

    return ". ".join(parts) + "."


# ── Action Generation ─────────────────────────────────────────────────

def generate_actions(
    db: Session,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[Action]:
    """Generate action items from current system state.

    This is idempotent: running twice produces no duplicate OPEN actions
    for the same entity.

    Safety: This creates action ITEMS only — it never executes actions.
    No applications are submitted, no emails are sent, no approvals bypassed.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    actions: list[Action] = []

    # 1. High-match opportunities that need review/apply
    actions.extend(_generate_opportunity_actions(db, now, dry_run))

    # 2. Outreach actions
    actions.extend(_generate_outreach_actions(db, now, dry_run))

    # 3. Follow-up actions
    actions.extend(_generate_followup_actions(db, now, dry_run))

    # 4. Deadline warning actions
    actions.extend(_generate_deadline_actions(db, now, dry_run))

    if not dry_run:
        db.flush()

    return actions


def _generate_opportunity_actions(
    db: Session, now: datetime, dry_run: bool
) -> list[Action]:
    """Generate actions for opportunities that need attention."""
    actions: list[Action] = []

    # Find opportunities with good match that haven't been applied to
    opportunities = (
        db.query(Opportunity)
        .filter(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 60,
        )
        .all()
    )

    for opp in opportunities:
        # Check if application exists
        existing_app = (
            db.query(Application)
            .filter(Application.opportunity_id == opp.id)
            .first()
        )

        # Check for existing open action for this opportunity
        existing_action = _find_existing_open_action(
            db, "opportunity", opp.id, ACTION_APPLY
        )
        existing_review = _find_existing_open_action(
            db, "opportunity", opp.id, ACTION_REVIEW_OPPORTUNITY
        )

        horizon = classify_horizon(opp.deadline, now)
        deadline_bucket = classify_deadline_bucket(opp.deadline, now)

        if existing_app is None or existing_app.status in ("NOT_APPLIED", "READY"):
            # Determine action type based on score
            if opp.match_score >= 80:
                action_type = ACTION_APPLY
                title = f"Apply to {opp.title}"
                if existing_action is not None:
                    continue
            else:
                action_type = ACTION_REVIEW_OPPORTUNITY
                title = f"Review {opp.title}"
                if existing_review is not None:
                    continue

            # Get company name
            company = db.get(Company, opp.company_id)
            company_name = company.name if company else "Unknown"

            # Calculate priority
            app_status = existing_app.status if existing_app else "NOT_APPLIED"
            priority = calculate_action_priority(
                match_score=opp.match_score,
                planning_horizon=horizon,
                deadline_bucket=deadline_bucket,
                application_status=app_status,
                now=now,
            )

            description = _build_action_description(
                action_type=action_type,
                company_name=company_name,
                opp=opp,
                horizon=horizon,
                deadline_bucket=deadline_bucket,
            )

            action = Action(
                action_type=action_type,
                priority=priority,
                entity_type="opportunity",
                entity_id=opp.id,
                title=title,
                description=description,
                status=ACTION_OPEN,
                source="action_center",
                due_at=opp.deadline,
                created_at=now,
                updated_at=now,
            )

            if not dry_run:
                db.add(action)
            actions.append(action)

    return actions


def _generate_outreach_actions(
    db: Session, now: datetime, dry_run: bool
) -> list[Action]:
    """Generate actions for outreach messages that need attention."""
    actions: list[Action] = []

    messages = db.query(Message).all()

    for msg in messages:
        if msg.status == "PENDING_APPROVAL":
            existing = _find_existing_open_action(
                db, "message", msg.id, ACTION_APPROVE_OUTREACH
            )
            if existing is not None:
                continue

            lead = db.get(Lead, msg.lead_id)
            recipient = lead.name if lead else "recipient"

            action = Action(
                action_type=ACTION_APPROVE_OUTREACH,
                priority=PRIORITY_P1,
                entity_type="message",
                entity_id=msg.id,
                title=f"Approve outreach to {recipient}",
                description=f"Draft message for {msg.opportunity_id} awaiting approval.",
                status=ACTION_OPEN,
                source="action_center",
                created_at=now,
                updated_at=now,
            )
            if not dry_run:
                db.add(action)
            actions.append(action)

        elif msg.status == "READY_TO_SEND":
            existing = _find_existing_open_action(
                db, "message", msg.id, ACTION_SEND_OUTREACH
            )
            if existing is not None:
                continue

            lead = db.get(Lead, msg.lead_id)
            recipient = lead.name if lead else "recipient"

            action = Action(
                action_type=ACTION_SEND_OUTREACH,
                priority=PRIORITY_P1,
                entity_type="message",
                entity_id=msg.id,
                title=f"Send outreach to {recipient}",
                description=f"Approved message for {msg.opportunity_id} ready to send.",
                status=ACTION_OPEN,
                source="action_center",
                created_at=now,
                updated_at=now,
            )
            if not dry_run:
                db.add(action)
            actions.append(action)

        elif msg.status == "DRAFT":
            existing = _find_existing_open_action(
                db, "message", msg.id, ACTION_REVIEW_OPPORTUNITY
            )
            if existing is not None:
                continue

            lead = db.get(Lead, msg.lead_id)
            recipient = lead.name if lead else "recipient"

            action = Action(
                action_type=ACTION_UPDATE_APPLICATION,
                priority=PRIORITY_P2,
                entity_type="message",
                entity_id=msg.id,
                title=f"Review outreach draft to {recipient}",
                description=f"Draft message for {msg.opportunity_id} can be reviewed.",
                status=ACTION_OPEN,
                source="action_center",
                created_at=now,
                updated_at=now,
            )
            if not dry_run:
                db.add(action)
            actions.append(action)

    return actions


def _generate_followup_actions(
    db: Session, now: datetime, dry_run: bool
) -> list[Action]:
    """Generate actions for follow-ups that are due."""
    actions: list[Action] = []

    due_followups = (
        db.query(FollowUp)
        .filter(FollowUp.status == "DUE")
        .all()
    )

    for fu in due_followups:
        existing = _find_existing_open_action(
            db, "followup", fu.id, ACTION_FOLLOW_UP
        )
        if existing is not None:
            continue

        action = Action(
            action_type=ACTION_FOLLOW_UP,
            priority=PRIORITY_P1,
            entity_type="followup",
            entity_id=fu.id,
            title=f"Follow up (ID: {fu.id})",
            description=f"Follow-up is due (scheduled: {fu.scheduled_for}).",
            status=ACTION_OPEN,
            source="action_center",
            due_at=fu.scheduled_for,
            created_at=now,
            updated_at=now,
        )
        if not dry_run:
            db.add(action)
        actions.append(action)

    return actions


def _generate_deadline_actions(
    db: Session, now: datetime, dry_run: bool
) -> list[Action]:
    """Generate deadline warning actions for opportunities approaching deadline."""
    actions: list[Action] = []

    # Find opportunities with deadlines within 7 days that haven't been applied to
    soon_deadline = now + timedelta(days=7)
    opportunities = (
        db.query(Opportunity)
        .filter(
            Opportunity.deadline.isnot(None),
            Opportunity.deadline <= soon_deadline,
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 40,
        )
        .all()
    )

    for opp in opportunities:
        existing_app = (
            db.query(Application)
            .filter(Application.opportunity_id == opp.id)
            .first()
        )

        # Only create deadline actions for unapplied opportunities
        if existing_app is not None and existing_app.status not in ("NOT_APPLIED", "READY"):
            continue

        bucket = classify_deadline_bucket(opp.deadline, now)
        if bucket not in ("OVERDUE", "TODAY", "WITHIN_3_DAYS", "WITHIN_7_DAYS"):
            continue

        existing = _find_existing_open_action(
            db, "opportunity", opp.id, ACTION_REVIEW_DEADLINE
        )
        if existing is not None:
            continue

        company = db.get(Company, opp.company_id)
        company_name = company.name if company else "Unknown"

        action = Action(
            action_type=ACTION_REVIEW_DEADLINE,
            priority=PRIORITY_P0 if bucket in ("OVERDUE", "TODAY") else PRIORITY_P1,
            entity_type="opportunity",
            entity_id=opp.id,
            title=f"Deadline {bucket.replace('_', ' ').lower()}: {opp.title}",
            description=f"{company_name} — {opp.title} deadline is {bucket.replace('_', ' ').lower()}.",
            status=ACTION_OPEN,
            source="action_center",
            due_at=opp.deadline,
            created_at=now,
            updated_at=now,
        )
        if not dry_run:
            db.add(action)
        actions.append(action)

    return actions


def _find_existing_open_action(
    db: Session,
    entity_type: str,
    entity_id: int,
    action_type: str,
) -> Action | None:
    """Find an existing open action for a specific entity to prevent duplicates."""
    return (
        db.query(Action)
        .filter(
            Action.entity_type == entity_type,
            Action.entity_id == entity_id,
            Action.action_type == action_type,
            Action.status.in_([ACTION_OPEN, ACTION_IN_PROGRESS]),
        )
        .first()
    )


def _build_action_description(
    *,
    action_type: str,
    company_name: str,
    opp: Opportunity,
    horizon: str,
    deadline_bucket: str,
) -> str:
    """Build a descriptive string for an action."""
    parts = [f"{company_name} — {opp.title}"]
    if horizon == HORIZON_SUMMER_2027:
        parts.append("Summer 2027")
    if deadline_bucket not in ("NO_DEADLINE", "FUTURE"):
        parts.append(f"Deadline {deadline_bucket.replace('_', ' ').lower()}")
    if opp.match_score is not None:
        parts.append(f"Match: {opp.match_score}/100")
    return ". ".join(parts)


# ── Action Management ─────────────────────────────────────────────────

def complete_action(db: Session, action_id: int) -> Action:
    """Mark an action as completed."""
    action = db.get(Action, action_id)
    if action is None:
        raise ValueError(f"Action {action_id} not found")
    if action.status in TERMINAL_ACTION_STATUSES:
        raise ValueError(f"Action {action_id} is already in terminal status: {action.status}")

    action.status = ACTION_COMPLETED
    action.completed_at = datetime.now(timezone.utc)
    action.updated_at = datetime.now(timezone.utc)
    db.flush()
    return action


def dismiss_action(db: Session, action_id: int) -> Action:
    """Dismiss an action."""
    action = db.get(Action, action_id)
    if action is None:
        raise ValueError(f"Action {action_id} not found")
    if action.status in TERMINAL_ACTION_STATUSES:
        raise ValueError(f"Action {action_id} is already in terminal status: {action.status}")

    action.status = ACTION_DISMISSED
    action.updated_at = datetime.now(timezone.utc)
    db.flush()
    return action


def start_action(db: Session, action_id: int) -> Action:
    """Mark an action as in-progress."""
    action = db.get(Action, action_id)
    if action is None:
        raise ValueError(f"Action {action_id} not found")
    if action.status in TERMINAL_ACTION_STATUSES:
        raise ValueError(f"Action {action_id} is already in terminal status: {action.status}")

    action.status = ACTION_IN_PROGRESS
    action.updated_at = datetime.now(timezone.utc)
    db.flush()
    return action


def list_actions(
    db: Session,
    *,
    status: str | None = None,
    action_type: str | None = None,
    priority: str | None = None,
    entity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Action]:
    """List actions with optional filters."""
    query = db.query(Action)
    if status is not None:
        query = query.filter(Action.status == status)
    if action_type is not None:
        query = query.filter(Action.action_type == action_type)
    if priority is not None:
        query = query.filter(Action.priority == priority)
    if entity_type is not None:
        query = query.filter(Action.entity_type == entity_type)

    # Sort: P0 first, then P1, P2, P3, then by due_at (NULLS LAST), then created_at
    return (
        query.order_by(
            Action.priority.asc(),
            Action.due_at.asc().nullslast(),
            Action.created_at.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_action_summary(db: Session) -> dict:
    """Get a summary of action states."""
    from sqlalchemy import func

    total = db.query(func.count(Action.id)).scalar() or 0

    by_status = dict(
        db.query(Action.status, func.count(Action.id))
        .group_by(Action.status)
        .all()
    )

    by_priority = dict(
        db.query(Action.priority, func.count(Action.id))
        .filter(Action.status == ACTION_OPEN)
        .group_by(Action.priority)
        .all()
    )

    by_type = dict(
        db.query(Action.action_type, func.count(Action.id))
        .filter(Action.status == ACTION_OPEN)
        .group_by(Action.action_type)
        .all()
    )

    return {
        "total_actions": total,
        "open": by_status.get(ACTION_OPEN, 0),
        "in_progress": by_status.get(ACTION_IN_PROGRESS, 0),
        "completed": by_status.get(ACTION_COMPLETED, 0),
        "dismissed": by_status.get(ACTION_DISMISSED, 0),
        "expired": by_status.get(ACTION_EXPIRED, 0),
        "by_priority": by_priority,
        "by_type": by_type,
    }


# ── Analytics ─────────────────────────────────────────────────────────

def get_application_analytics(db: Session) -> dict:
    """Deterministic application analytics from real data."""
    from sqlalchemy import func

    # Total counts by status
    status_counts = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    total = sum(status_counts.values())

    # Average match score of applied opportunities
    avg_score = (
        db.query(func.avg(Opportunity.match_score))
        .join(Application, Application.opportunity_id == Opportunity.id)
        .filter(Opportunity.match_score.isnot(None))
        .scalar()
    )

    # Applications by source (via opportunity → company)
    # Applications by opportunity type
    type_counts = dict(
        db.query(Opportunity.type, func.count(Application.id))
        .join(Application, Application.opportunity_id == Opportunity.id)
        .group_by(Opportunity.type)
        .all()
    )

    # Applications by planning horizon
    horizon_counts: dict[str, int] = {}
    applications = db.query(Application).all()
    now = datetime.now(timezone.utc)
    for app_record in applications:
        opp = db.get(Opportunity, app_record.opportunity_id)
        if opp:
            horizon = classify_horizon(opp.deadline, now)
            horizon_counts[horizon] = horizon_counts.get(horizon, 0) + 1

    # Derived rates
    applied = status_counts.get("APPLIED", 0) + status_counts.get("ASSESSMENT", 0) + \
        status_counts.get("INTERVIEW", 0) + status_counts.get("FINAL_ROUND", 0) + \
        status_counts.get("OFFER", 0) + status_counts.get("ACCEPTED", 0) + \
        status_counts.get("REJECTED", 0)

    interviews = status_counts.get("INTERVIEW", 0) + status_counts.get("FINAL_ROUND", 0)
    offers = status_counts.get("OFFER", 0) + status_counts.get("ACCEPTED", 0)
    rejections = status_counts.get("REJECTED", 0)

    return {
        "total": total,
        "by_status": status_counts,
        "by_type": type_counts,
        "by_horizon": horizon_counts,
        "average_match_score": round(float(avg_score), 1) if avg_score else None,
        "interview_rate": round(interviews / applied, 3) if applied > 0 else None,
        "offer_rate": round(offers / applied, 3) if applied > 0 else None,
        "rejection_rate": round(rejections / applied, 3) if applied > 0 else None,
    }
