"""Automation scheduler — application-level background scheduler.

Uses asyncio for lightweight scheduling within the FastAPI process.
Designed so the orchestration logic can later move to Celery/RQ/Temporal
without rewriting the business logic.

Behavior:
- Runs one automation cycle immediately on startup (if enabled)
- Then runs cycles at the configured interval
- Prevents overlapping scheduled runs via an asyncio.Lock
- Survives individual cycle failures — keeps scheduling
- Cancels cleanly on application shutdown
- Manual runs go through the same lock to avoid corrupting shared state
"""

from __future__ import annotations

import asyncio
import logging

from app.automation.engine import run_automation_cycle
from app.automation.models import AutomationRunResult, RunTrigger
from app.core.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Lightweight in-process scheduler for automation runs.

    Lifecycle:
        start() → immediate run → sleep(interval) → run → sleep → …
        stop()  → cancels the loop task, sets _running = False

    Safety:
        - An asyncio.Lock prevents overlapping scheduled runs
        - A failed cycle is logged and the loop continues
        - stop() cancels the task without blocking
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_run: AutomationRunResult | None = None
        self._run_lock = asyncio.Lock()

    @property
    def is_active(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    @property
    def last_run(self) -> AutomationRunResult | None:
        return self._last_run

    def start(self) -> None:
        """Start the scheduler if automation is enabled.

        The first automation cycle runs immediately (no initial sleep).
        """
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
        """Stop the scheduler gracefully.

        Sets the running flag to False and cancels the background task.
        Does not block — the task will raise CancelledError on next await.
        """
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("Automation scheduler stop requested")
        self._task = None

    async def _run_loop(self) -> None:
        """Main scheduler loop.

        Runs one cycle immediately, then sleeps for the configured interval
        before running the next cycle.  Uses an asyncio.Lock so only one
        scheduled run executes at a time.
        """
        while self._running:
            try:
                settings = get_settings()

                if not settings.automation_enabled:
                    logger.info("Automation disabled — scheduler stopping")
                    break

                interval_seconds = settings.automation_scheduler_interval_minutes * 60

                # ── Run the cycle (with overlap protection) ──────────
                await self._execute_scheduled_cycle(settings)

                if not self._running:
                    break

                # ── Sleep until next cycle ───────────────────────────
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    logger.info("Automation scheduler sleep cancelled — shutting down")
                    break

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

    async def _execute_scheduled_cycle(self, settings: object) -> None:
        """Execute one scheduled automation cycle with overlap protection.

        If a cycle is already running (manual or scheduled), this call
        logs a skip and returns immediately.
        """
        if self._run_lock.locked():
            logger.info("Skipping scheduled automation run — previous run still active")
            return

        async with self._run_lock:
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

    async def execute_manual_run(
        self,
        *,
        dry_run: bool = False,
        source_override: str | None = None,
    ) -> AutomationRunResult:
        """Execute a manual automation run.

        Uses the same lock as scheduled runs to prevent corruption
        of shared state.  Returns the run result directly.
        """
        async with self._run_lock:
            db = SessionLocal()
            try:
                result = await run_automation_cycle(
                    db,
                    trigger=RunTrigger.MANUAL,
                    dry_run=dry_run,
                    source_override=source_override,
                )
                self._last_run = result
                return result
            finally:
                db.close()


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
