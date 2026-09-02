"""Automation orchestrator — the core automation engine.

Orchestrates the full pipeline:
  discovery → normalization → deduplication → ingestion → matching → planning → AI enrichment → draft preparation

Safety rules:
- NEVER sends emails — requires explicit human approval
- NEVER approves drafts automatically
- AI is optional — deterministic matching is always authoritative
- Idempotent — repeated runs with no new data produce no duplicates
- One source failure doesn't stop others
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.automation.models import (
    AutomationRunResult,
    RunStatus,
    RunTrigger,
    SourceResult,
)
from app.core.config import get_settings
from app.models.automation_run import AutomationRun
from app.discovery.registry import list_source_names
from app.models.followup import FollowUp as FollowUpModel
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.services.action_center import generate_actions
from app.services.discovery import ingest, run_source
from app.services.followup import check_and_mark_due
from app.services.matching import rank_opportunities
from app.services.planning import classify_horizon

logger = logging.getLogger(__name__)

# ── High-value threshold (configurable via settings) ───────────────────────
_HIGH_MATCH_DEFAULT = 80


def _parse_sources(raw: str) -> list[str]:
    """Parse comma-separated source names from config."""
    return [s.strip() for s in raw.split(",") if s.strip()]


async def run_automation_cycle(
    db: Session,
    *,
    trigger: RunTrigger = RunTrigger.MANUAL,
    dry_run: bool = False,
    source_override: str | None = None,
) -> AutomationRunResult:
    """Execute one full automation cycle.

    This is the single orchestration entry point used by both:
    1. Manual trigger (POST /automation/run)
    2. Automatic scheduler

    Args:
        db: Database session.
        trigger: How this run was initiated.
        dry_run: If True, discover but don't persist.
        source_override: If set, run only this source (ignoring config list).

    Returns:
        A complete AutomationRunResult with all counts.
    """
    settings = get_settings()
    run = AutomationRunResult(
        run_id=str(uuid.uuid4())[:12],
        trigger=trigger,
        dry_run=dry_run,
    )

    trigger_val = trigger.value if hasattr(trigger, "value") else str(trigger)
    logger.info(
        "Automation run started: id=%s trigger=%s dry_run=%s",
        run.run_id, trigger_val, dry_run,
    )

    try:
        # ── Phase 1: Discovery ────────────────────────────────────
        if settings.automation_discovery_enabled:
            _run_discovery(db, run, settings, source_override)

        # ── Phase 2: Matching / Scoring ───────────────────────────
        if settings.automation_matching_enabled:
            _run_matching(db, run, settings)

        # ── Phase 3: Planning ─────────────────────────────────────
        _run_planning(db, run)

        # ── Phase 4: Follow-up processing ─────────────────────────
        if settings.automation_followup_processing_enabled:
            _run_followup_processing(db, run)

        # ── Phase 5: Action generation ────────────────────────────
        _run_action_generation(db, run)

        # ── Phase 6: Notification sync ────────────────────────────
        _run_notification_sync(db, run)

        run.complete()

    except Exception as exc:
        logger.error("Automation run failed: %s", exc)
        run.fail(str(exc))

    # Persist the run record
    try:
        _persist_run(db, run)
    except Exception as exc:
        logger.warning("Failed to persist automation run: %s", exc)

    status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
    logger.info(
        "Automation run completed: id=%s status=%s created=%d scored=%d",
        run.run_id, status_val, run.opportunities_created,
        run.opportunities_scored,
    )

    return run


def _run_discovery(
    db: Session,
    run: AutomationRunResult,
    settings: object,
    source_override: str | None = None,
) -> None:
    """Run discovery through all configured (or overridden) sources."""
    if source_override:
        sources = [source_override]
    else:
        sources = _parse_sources(settings.automation_sources)

    run.sources_attempted = len(sources)

    for source_name in sources:
        logger.info("Discovery source starting: %s", source_name)

        try:
            # In dry-run mode, we still fetch and normalize
            # but we check the existing dedup rather than persisting
            if run.dry_run:
                source_result = _dry_run_source(db, source_name, settings)
            else:
                ingestion = run_source(db, source_name)
                # Convert IngestionResult to SourceResult
                source_result = SourceResult(
                    source_name=ingestion.source_name,
                    raw_count=ingestion.raw_count,
                    ingested=ingestion.ingested,
                    duplicates_skipped=ingestion.duplicates_skipped,
                    companies_created=ingestion.companies_created,
                    success=len(ingestion.errors) == 0,
                    errors=ingestion.errors,
                )

            run.source_results.append(source_result)

            if source_result.success:
                run.sources_succeeded += 1
            else:
                run.sources_failed += 1

            run.opportunities_seen += source_result.raw_count
            run.opportunities_created += source_result.ingested
            run.opportunities_deduplicated += source_result.duplicates_skipped

            logger.info(
                "Discovery source completed: %s ingested=%d dedup=%d",
                source_name, source_result.ingested, source_result.duplicates_skipped,
            )

        except Exception as exc:
            logger.error("Discovery source failed: %s — %s", source_name, exc)
            run.sources_failed += 1
            run.source_results.append(SourceResult(
                source_name=source_name,
                success=False,
                errors=[str(exc)],
            ))


def _dry_run_source(
    db: Session,
    source_name: str,
    settings: object,
) -> SourceResult:
    """Run a source adapter in dry-run mode (no DB mutations).

    Fetches, normalizes, deduplicates — but doesn't persist.
    Counts would-be creations vs. duplicates.
    """
    from app.discovery.deduplicator import deduplicate
    from app.discovery.models import IngestionResult
    from app.discovery.normalizer import normalize_all
    from app.discovery.registry import create_adapter

    try:
        adapter = create_adapter(source_name)
    except ValueError as exc:
        return SourceResult(
            source_name=source_name,
            success=False,
            errors=[str(exc)],
        )

    try:
        raw_items = adapter.discover()
    except Exception as exc:
        return SourceResult(
            source_name=source_name,
            success=False,
            errors=[f"Adapter discover() failed: {exc!s}"],
        )

    if not raw_items:
        return SourceResult(source_name=source_name, raw_count=0)

    normalized = normalize_all(raw_items)
    unique = deduplicate(normalized)

    from app.services.discovery import _is_duplicate

    ingested = 0
    duplicates = 0
    for item in unique:
        if _is_duplicate(db, item):
            duplicates += 1
        else:
            ingested += 1

    return SourceResult(
        source_name=source_name,
        raw_count=len(normalized),
        ingested=ingested,
        duplicates_skipped=duplicates + (len(normalized) - len(unique)),
    )


def _run_matching(
    db: Session,
    run: AutomationRunResult,
    settings: object,
) -> None:
    """Score un-scored opportunities and count high-match ones."""
    # Find opportunities that haven't been scored yet
    unscored = (
        db.query(Opportunity)
        .filter(Opportunity.match_score.is_(None))
        .limit(settings.automation_max_opportunities_per_run)
        .all()
    )

    # Get the default profile for matching
    profile = db.query(Profile).first()
    if profile is None:
        logger.info("No profile found — skipping matching")
        return

    min_score = settings.automation_min_match_score

    for opp in unscored:
        try:
            from app.services.matching import match_opportunity
            result = match_opportunity(db, profile, opp)

            opp.match_score = result.score
            db.flush()

            run.opportunities_scored += 1
            if result.score >= min_score:
                run.high_match_count += 1

        except Exception as exc:
            logger.warning("Matching failed for opportunity %d: %s", opp.id, exc)
            run.errors.append(f"Matching failed for opp {opp.id}: {exc!s}")

    db.flush()


def _run_planning(db: Session, run: AutomationRunResult) -> None:
    """Classify all opportunities into planning horizons."""
    now = datetime.now(timezone.utc)
    opportunities = db.query(Opportunity).all()

    for opp in opportunities:
        horizon = classify_horizon(opp.deadline, now)
        if horizon == "NOW":
            run.now_count += 1
        elif horizon == "UPCOMING":
            run.upcoming_count += 1
        elif horizon == "SUMMER_2027":
            run.summer_2027_count += 1
        elif horizon == "FUTURE":
            run.future_count += 1
        else:
            run.unknown_count += 1


def _run_followup_processing(db: Session, run: AutomationRunResult) -> None:
    """Find PENDING follow-ups whose scheduled time has arrived, mark DUE."""
    pending_followups = (
        db.query(FollowUpModel)
        .filter(FollowUpModel.status == "PENDING")
        .all()
    )

    now = datetime.now(timezone.utc)

    for fu in pending_followups:
        if fu.scheduled_for <= now:
            try:
                check_and_mark_due(db, fu)
                run.followups_marked_due += 1
            except Exception as exc:
                logger.warning("Follow-up mark-due failed for %d: %s", fu.id, exc)
                run.errors.append(f"Follow-up {fu.id} mark-due failed: {exc!s}")


def _run_action_generation(db: Session, run: AutomationRunResult) -> None:
    """Generate action items from current system state.

    This is safe: it creates action ITEMS only.
    It never submits applications, sends emails, or approves outreach.
    """
    try:
        actions = generate_actions(db, dry_run=False)
        run.actions_generated = len(actions)
        db.flush()
        logger.info("Action generation: %d actions created", len(actions))
    except Exception as exc:
        logger.warning("Action generation failed: %s", exc)
        run.errors.append(f"Action generation failed: {exc!s}")


def _run_notification_sync(db: Session, run: AutomationRunResult) -> None:
    """Synchronize notifications from current system state.

    This is safe: it creates attention/notification records only.
    It never sends emails, never applies, never approves.
    Notification sync is idempotent — repeated runs don't create duplicates.
    """
    try:
        from app.services.notifications import sync_notifications
        result = sync_notifications(db)
        run.notifications_generated = result.get("created", 0)
        db.flush()
        logger.info("Notification sync: %d created", run.notifications_generated)
    except Exception as exc:
        logger.warning("Notification sync failed: %s", exc)
        run.errors.append(f"Notification sync failed: {exc!s}")


def _persist_run(db: Session, run: AutomationRunResult) -> None:
    """Persist the AutomationRunResult to the automation_runs table.

    If persistence fails, log the error but do not fail the run itself.
    The intelligence pipeline already completed successfully.
    """
    try:
        error_summary = None
        if run.errors:
            # Store only safe, human-readable error messages
            safe_errors = [e for e in run.errors if len(e) < 500]
            error_summary = "; ".join(safe_errors[:10]) if safe_errors else None

        trigger_val = run.trigger.value if hasattr(run.trigger, "value") else str(run.trigger)
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)

        db_run = AutomationRun(
            run_id=run.run_id,
            trigger=trigger_val,
            status=status_val,
            dry_run=run.dry_run,
            started_at=run.started_at,
            completed_at=run.completed_at,
            sources_attempted=run.sources_attempted,
            sources_succeeded=run.sources_succeeded,
            sources_failed=run.sources_failed,
            opportunities_seen=run.opportunities_seen,
            opportunities_created=run.opportunities_created,
            opportunities_deduplicated=run.opportunities_deduplicated,
            opportunities_scored=run.opportunities_scored,
            high_match_count=run.high_match_count,
            summer_2027_count=run.summer_2027_count,
            now_count=run.now_count,
            upcoming_count=run.upcoming_count,
            future_count=run.future_count,
            unknown_count=run.unknown_count,
            actions_generated=run.actions_generated,
            notifications_generated=run.notifications_generated,
            followups_marked_due=run.followups_marked_due,
            error_summary=error_summary,
        )
        db.add(db_run)
        db.flush()
    except Exception as exc:
        logger.warning("Failed to persist automation run: %s", exc)
        # Do not re-raise — the run itself completed


def get_automation_status() -> dict:
    """Get current automation engine status."""
    settings = get_settings()
    return {
        "enabled": settings.automation_enabled,
        "scheduler_active": settings.automation_enabled,
        "scheduler_interval_minutes": settings.automation_scheduler_interval_minutes,
        "discovery_enabled": settings.automation_discovery_enabled,
        "matching_enabled": settings.automation_matching_enabled,
        "ai_insights_enabled": settings.automation_ai_insights_enabled and bool(settings.ai_api_key),
        "outreach_drafts_enabled": settings.automation_outreach_drafts_enabled,
        "followup_processing_enabled": settings.automation_followup_processing_enabled,
        "sources": _parse_sources(settings.automation_sources),
        "min_match_score": settings.automation_min_match_score,
        "max_opportunities_per_run": settings.automation_max_opportunities_per_run,
        "max_drafts_per_run": settings.automation_max_drafts_per_run,
        "dry_run_default": settings.automation_dry_run,
    }
