"""Application lifecycle + Action Center API routes.

Provides:
- Application CRUD + state machine transitions
- Action Center: list, filter, complete, dismiss, start
- Triage: deterministic assessment of individual opportunities
- Analytics: application analytics from real data

Safety: No endpoints automatically apply, send, or approve anything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.application import APPLICATION_TRANSITIONS, TERMINAL_STATUSES
from app.services.action_center import (
    ACTION_COMPLETED,
    ACTION_DISMISSED,
    ACTION_IN_PROGRESS,
    get_action_summary,
    get_application_analytics,
    generate_actions,
    triage_opportunity,
    list_actions,
    complete_action,
    dismiss_action,
    start_action,
)
from app.services.application import (
    create_application,
    get_application,
    get_application_with_context,
    list_applications,
    transition_application,
    count_applications_by_status,
)
from app.models.opportunity import Opportunity

router = APIRouter()


# ── Application schemas ───────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    opportunity_id: int
    lead_id: int | None = None
    application_url: str | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    notes: str | None = None
    application_url: str | None = None


class ApplicationTransition(BaseModel):
    notes: str | None = None
    rejection_reason: str | None = None


class ActionUpdate(BaseModel):
    pass


# ── Application endpoints ─────────────────────────────────────────────

@router.get("/applications")
def list_applications_route(
    status: str | None = None,
    opportunity_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List applications with optional filters."""
    apps = list_applications(
        db, status=status, opportunity_id=opportunity_id, limit=limit, offset=offset
    )
    return [
        {
            "id": a.id,
            "opportunity_id": a.opportunity_id,
            "lead_id": a.lead_id,
            "status": a.status,
            "application_url": a.application_url,
            "notes": a.notes,
            "rejection_reason": a.rejection_reason,
            "applied_at": a.applied_at.isoformat() if a.applied_at else None,
            "last_status_change_at": a.last_status_change_at.isoformat() if a.last_status_change_at else None,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        for a in apps
    ]


@router.post("/applications")
def create_application_route(
    body: ApplicationCreate,
    db: Session = Depends(get_db),
):
    """Create a new application in NOT_APPLIED status."""
    try:
        app = create_application(
            db,
            opportunity_id=body.opportunity_id,
            lead_id=body.lead_id,
            application_url=body.application_url,
            notes=body.notes,
        )
        db.commit()
        return {
            "id": app.id,
            "opportunity_id": app.opportunity_id,
            "lead_id": app.lead_id,
            "status": app.status,
            "application_url": app.application_url,
            "notes": app.notes,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/applications/{application_id}")
def get_application_route(
    application_id: int,
    db: Session = Depends(get_db),
):
    """Get application with context."""
    ctx = get_application_with_context(db, application_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Application not found")

    app = ctx["application"]
    opp = ctx["opportunity"]
    company = ctx["company"]

    return {
        "id": app.id,
        "opportunity_id": app.opportunity_id,
        "lead_id": app.lead_id,
        "status": app.status,
        "application_url": app.application_url,
        "notes": app.notes,
        "rejection_reason": app.rejection_reason,
        "applied_at": app.applied_at.isoformat() if app.applied_at else None,
        "last_status_change_at": app.last_status_change_at.isoformat() if app.last_status_change_at else None,
        "created_at": app.created_at.isoformat(),
        "updated_at": app.updated_at.isoformat(),
        "opportunity": {
            "id": opp.id,
            "title": opp.title,
            "type": opp.type,
            "status": opp.status,
            "match_score": opp.match_score,
            "deadline": opp.deadline.isoformat() if opp.deadline else None,
        } if opp else None,
        "company": {
            "id": company.id,
            "name": company.name,
        } if company else None,
    }


@router.patch("/applications/{application_id}")
def update_application_route(
    application_id: int,
    body: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    """Update application notes/url (not status)."""
    app = get_application(db, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if body.notes is not None:
        app.notes = body.notes
    if body.application_url is not None:
        app.application_url = body.application_url
    db.flush()
    db.commit()

    return {
        "id": app.id,
        "status": app.status,
        "notes": app.notes,
        "application_url": app.application_url,
    }


# ── Application state machine transitions ──────────────────────────────

def _transition_route(application_id: int, target_status: str, body: ApplicationTransition, db: Session):
    """Common transition handler."""
    try:
        app = transition_application(
            db,
            application_id,
            target_status,
            notes=body.notes,
            rejection_reason=body.rejection_reason,
        )
        db.commit()
        return {
            "id": app.id,
            "status": app.status,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "last_status_change_at": app.last_status_change_at.isoformat() if app.last_status_change_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/applications/{application_id}/ready")
def ready_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "READY", body, db)


@router.post("/applications/{application_id}/apply")
def apply_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "APPLIED", body, db)


@router.post("/applications/{application_id}/assessment")
def assessment_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "ASSESSMENT", body, db)


@router.post("/applications/{application_id}/interview")
def interview_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "INTERVIEW", body, db)


@router.post("/applications/{application_id}/final_round")
def final_round_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "FINAL_ROUND", body, db)


@router.post("/applications/{application_id}/offer")
def offer_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "OFFER", body, db)


@router.post("/applications/{application_id}/accept")
def accept_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "ACCEPTED", body, db)


@router.post("/applications/{application_id}/reject")
def reject_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "REJECTED", body, db)


@router.post("/applications/{application_id}/withdraw")
def withdraw_application(application_id: int, body: ApplicationTransition = ApplicationTransition(), db: Session = Depends(get_db)):
    return _transition_route(application_id, "WITHDRAWN", body, db)


@router.get("/applications/{application_id}/transitions")
def get_valid_transitions(application_id: int, db: Session = Depends(get_db)):
    """Return the valid transitions for a given application."""
    app = get_application(db, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    return {
        "current_status": app.status,
        "valid_transitions": APPLICATION_TRANSITIONS.get(app.status, []),
        "is_terminal": app.status in TERMINAL_STATUSES,
    }


# ── Action Center endpoints ───────────────────────────────────────────

@router.get("/actions")
def list_actions_route(
    status: str | None = None,
    action_type: str | None = None,
    priority: str | None = None,
    entity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List actions with optional filters, sorted by priority."""
    actions = list_actions(
        db,
        status=status,
        action_type=action_type,
        priority=priority,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "priority": a.priority,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "title": a.title,
            "description": a.description,
            "status": a.status,
            "source": a.source,
            "due_at": a.due_at.isoformat() if a.due_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in actions
    ]


@router.get("/actions/summary")
def action_summary(db: Session = Depends(get_db)):
    """Get action center summary with counts by status, priority, and type."""
    return get_action_summary(db)


@router.get("/actions/{action_id}")
def get_action_route(action_id: int, db: Session = Depends(get_db)):
    """Get a single action."""
    from app.models.application import Action
    action = db.get(Action, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    return {
        "id": action.id,
        "action_type": action.action_type,
        "priority": action.priority,
        "entity_type": action.entity_type,
        "entity_id": action.entity_id,
        "title": action.title,
        "description": action.description,
        "status": action.status,
        "source": action.source,
        "due_at": action.due_at.isoformat() if action.due_at else None,
        "completed_at": action.completed_at.isoformat() if action.completed_at else None,
        "created_at": action.created_at.isoformat(),
    }


@router.post("/actions/{action_id}/complete")
def complete_action_route(action_id: int, db: Session = Depends(get_db)):
    """Mark an action as completed."""
    try:
        action = complete_action(db, action_id)
        db.commit()
        return {"id": action.id, "status": action.status, "completed_at": action.completed_at.isoformat()}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/actions/{action_id}/dismiss")
def dismiss_action_route(action_id: int, db: Session = Depends(get_db)):
    """Dismiss an action."""
    try:
        action = dismiss_action(db, action_id)
        db.commit()
        return {"id": action.id, "status": action.status}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/actions/{action_id}/start")
def start_action_route(action_id: int, db: Session = Depends(get_db)):
    """Mark an action as in-progress."""
    try:
        action = start_action(db, action_id)
        db.commit()
        return {"id": action.id, "status": action.status}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/actions/generate")
def generate_actions_route(
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    """Generate action items from current system state.

    Idempotent: running twice produces no duplicate OPEN actions.
    Dry run: returns what would be created without persisting.
    """
    actions = generate_actions(db, dry_run=dry_run)
    if not dry_run:
        db.commit()
    return {
        "generated": len(actions),
        "dry_run": dry_run,
        "actions": [
            {
                "action_type": a.action_type,
                "priority": a.priority,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "title": a.title,
            }
            for a in actions
        ],
    }


# ── Triage endpoint ───────────────────────────────────────────────────

@router.get("/opportunities/{opportunity_id}/triage")
def triage_opportunity_route(opportunity_id: int, db: Session = Depends(get_db)):
    """Deterministic triage assessment for a single opportunity."""
    opp = db.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    result = triage_opportunity(db, opp)
    return result


# ── Analytics endpoint ────────────────────────────────────────────────

@router.get("/applications/analytics/summary")
def application_analytics_route(db: Session = Depends(get_db)):
    """Deterministic application analytics from real data."""
    return get_application_analytics(db)
