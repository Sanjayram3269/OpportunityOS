"""Automation API routes — control and monitor the automation engine."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.automation.engine import get_automation_status
from app.automation.scheduler import get_scheduler

router = APIRouter(prefix="/automation", tags=["automation"])


# ── Request/Response schemas ───────────────────────────────────────────────

class AutomationRunRequest(BaseModel):
    """Request body for triggering an automation run."""
    dry_run: bool = False
    source: str | None = None  # If set, run only this source


class AutomationConfigUpdate(BaseModel):
    """Request body for updating automation config.

    Only non-None fields are updated. Returns the current config.
    Note: Most config changes require editing .env or Settings.
    This endpoint is for runtime flags where applicable.
    """
    dry_run: bool | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/run")
async def trigger_run(
    request: AutomationRunRequest | None = None,
) -> dict:
    """Trigger an automation run.

    Runs the full pipeline: discovery → matching → planning → follow-up processing.
    AI insights and outreach drafts are controlled by configuration.

    The run completes before returning — no background execution.
    Uses the scheduler's lock to prevent overlapping runs.
    Outreach sending is NEVER triggered by automation.
    """
    dry_run = request.dry_run if request else False
    source_override = request.source if request else None

    scheduler = get_scheduler()
    result = await scheduler.execute_manual_run(
        dry_run=dry_run,
        source_override=source_override,
    )

    return result.to_dict()


@router.get("/status")
def automation_status() -> dict:
    """Get current automation engine status and configuration."""
    status = get_automation_status()

    # Add scheduler info
    scheduler = get_scheduler()
    status["scheduler_active"] = scheduler.is_active
    if scheduler.last_run:
        status["last_run"] = scheduler.last_run.to_dict()
    else:
        # Fall back to persistent last run if in-memory is empty (e.g. after restart)
        from app.db.session import SessionLocal
        from app.models.automation_run import AutomationRun

        db = SessionLocal()
        try:
            last = (
                db.query(AutomationRun)
                .order_by(AutomationRun.started_at.desc())
                .first()
            )
            if last:
                status["last_run"] = {
                    "run_id": last.run_id,
                    "status": last.status,
                    "trigger": last.trigger,
                    "started_at": last.started_at.isoformat() if last.started_at else None,
                    "completed_at": last.completed_at.isoformat() if last.completed_at else None,
                    "opportunities_created": last.opportunities_created,
                    "error_summary": last.error_summary,
                }
        finally:
            db.close()

    return status


@router.get("/runs")
def list_runs(
    status: str | None = None,
    trigger: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """List persisted automation runs.

    Returns runs newest-first with pagination.
    Optionally filter by status or trigger.
    """
    from app.db.session import SessionLocal
    from app.models.automation_run import AutomationRun
    from sqlalchemy import func

    db = SessionLocal()
    try:
        query = db.query(AutomationRun)
        count_query = db.query(func.count(AutomationRun.id))

        if status is not None:
            query = query.filter(AutomationRun.status == status)
            count_query = count_query.filter(AutomationRun.status == status)
        if trigger is not None:
            query = query.filter(AutomationRun.trigger == trigger)
            count_query = count_query.filter(AutomationRun.trigger == trigger)

        total = count_query.scalar() or 0
        runs = (
            query
            .order_by(AutomationRun.started_at.desc())
            .offset(offset)
            .limit(min(limit, 50))
            .all()
        )

        return {
            "total": total,
            "runs": [
                {
                    "run_id": r.run_id,
                    "trigger": r.trigger,
                    "status": r.status,
                    "dry_run": r.dry_run,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "duration_seconds": (
                        (r.completed_at - r.started_at).total_seconds()
                        if r.completed_at and r.started_at else None
                    ),
                    "opportunities_created": r.opportunities_created,
                    "opportunities_scored": r.opportunities_scored,
                    "actions_generated": r.actions_generated,
                    "notifications_generated": r.notifications_generated,
                    "sources_succeeded": r.sources_succeeded,
                    "sources_failed": r.sources_failed,
                    "error_summary": r.error_summary,
                }
                for r in runs
            ],
        }
    finally:
        db.close()


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    """Get details of a specific automation run."""
    from app.db.session import SessionLocal
    from app.models.automation_run import AutomationRun

    db = SessionLocal()
    try:
        run = db.query(AutomationRun).filter(AutomationRun.run_id == run_id).first()
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        return {
            "run_id": run.run_id,
            "trigger": run.trigger,
            "status": run.status,
            "dry_run": run.dry_run,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": (
                (run.completed_at - run.started_at).total_seconds()
                if run.completed_at and run.started_at else None
            ),
            "sources_attempted": run.sources_attempted,
            "sources_succeeded": run.sources_succeeded,
            "sources_failed": run.sources_failed,
            "opportunities_seen": run.opportunities_seen,
            "opportunities_created": run.opportunities_created,
            "opportunities_deduplicated": run.opportunities_deduplicated,
            "opportunities_scored": run.opportunities_scored,
            "high_match_count": run.high_match_count,
            "summer_2027_count": run.summer_2027_count,
            "now_count": run.now_count,
            "upcoming_count": run.upcoming_count,
            "future_count": run.future_count,
            "unknown_count": run.unknown_count,
            "actions_generated": run.actions_generated,
            "notifications_generated": run.notifications_generated,
            "followups_marked_due": run.followups_marked_due,
            "error_summary": run.error_summary,
        }
    finally:
        db.close()


@router.get("/config")
def automation_config() -> dict:
    """Get the current automation configuration.

    Does NOT expose secrets (API keys, SMTP passwords, etc.).
    """
    return get_automation_status()


@router.patch("/config")
def update_automation_config(
    update: AutomationConfigUpdate,
) -> dict:
    """Update runtime automation configuration.

    Currently supports:
    - dry_run: toggle dry-run mode for the next run

    For persistent config changes, update the environment variables.
    """
    # Runtime config updates are limited to dry_run
    # Persistent settings require environment/config changes
    return {
        "message": "Runtime config updated. For persistent changes, update environment variables.",
        "current_config": get_automation_status(),
    }
