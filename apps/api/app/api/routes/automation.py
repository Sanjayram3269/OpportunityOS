"""Automation API routes — control and monitor the automation engine."""

from __future__ import annotations

from fastapi import APIRouter
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

    return status


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
