"""Automation scheduler — application-level background scheduler.

Uses asyncio for lightweight scheduling within the FastAPI process.
Designed so the orchestration logic can later move to Celery/RQ/Temporal
without rewriting the business logic.

Safety:
- Only runs when automation_enabled is True
- Uses the same run_automation_cycle() as manual trigger
- Never bypasses human approval for outreach
- Gracefully handles scheduler errors
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.automation.engine import run_automation_cycle
from app.automation.models import AutomationRunResult, RunTrigger
from app.core.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Lightweight in-process scheduler for automation runs.

    Usage:
        scheduler = AutomationScheduler()
        # On FastAPI startup:
        scheduler.start()
        # On FastAPI shutdown:
        scheduler.stop()
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_run: AutomationRunResult | None = None

    @property
    def is_active(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    @property
    def last_run(self) -> AutomationRunResult | None:
        return self._last_run

    def start(self) -> None:
        """Start the scheduler if automation is enabled."""
        settings = get_settings()
        if not settings.automation_enabled:
            logger.info("Automation scheduler not started — automation is disabled")
            return

        if self._running:
            logger.info("Automation scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Automation scheduler started — interval=%d minutes",
            settings.automation_scheduler_interval_minutes,
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("Automation scheduler stopped")
        self._task = None

    async def _run_loop(self) -> None:
        """Main scheduler loop — runs automation cycles periodically."""
        while self._running:
            try:
                settings = get_settings()

                if not settings.automation_enabled:
                    logger.info("Automation disabled — scheduler pausing")
                    break

                interval_seconds = settings.automation_scheduler_interval_minutes * 60

                # Wait for the configured interval
                await asyncio.sleep(interval_seconds)

                if not self._running:
                    break

                # Run the automation cycle
                db = SessionLocal()
                try:
                    result = await run_automation_cycle(
                        db,
                        trigger=RunTrigger.SCHEDULER,
                        dry_run=settings.automation_dry_run,
                    )
                    self._last_run = result

                    logger.info(
                        "Scheduled automation run completed: id=%s status=%s created=%d",
                        result.run_id, result.status.value, result.opportunities_created,
                    )
                except Exception as exc:
                    logger.error("Scheduled automation run failed: %s", exc)
                finally:
                    db.close()

            except asyncio.CancelledError:
                logger.info("Automation scheduler cancelled")
                break
            except Exception as exc:
                logger.error("Automation scheduler error: %s", exc)
                # Continue the loop — don't let one error kill the scheduler
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    break


# ── Global scheduler instance ─────────────────────────────────────────────

_scheduler: AutomationScheduler | None = None


def get_scheduler() -> AutomationScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AutomationScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global automation scheduler."""
    get_scheduler().start()


def stop_scheduler() -> None:
    """Stop the global automation scheduler."""
    get_scheduler().stop()
