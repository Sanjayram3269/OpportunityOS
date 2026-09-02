"""Automation result models — typed dataclasses for run results.

No database table. Automation runs are in-memory results tracked
via the last-run status endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class RunTrigger(str, Enum):
    """How the automation run was triggered."""
    MANUAL = "MANUAL"
    SCHEDULER = "SCHEDULER"


class RunStatus(str, Enum):
    """Status of an automation run."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class SourceResult:
    """Result for a single discovery source within a run."""
    source_name: str
    raw_count: int = 0
    ingested: int = 0
    duplicates_skipped: int = 0
    companies_created: int = 0
    success: bool = True
    errors: list[str] = field(default_factory=list)


@dataclass
class AutomationRunResult:
    """Complete result of one automation execution.

    This is the primary output of the orchestrator.
    It captures everything that happened during the run.
    """
    run_id: str = ""
    status: RunStatus = RunStatus.RUNNING
    trigger: RunTrigger = RunTrigger.MANUAL
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # Discovery
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    source_results: list[SourceResult] = field(default_factory=list)

    # Ingestion
    opportunities_seen: int = 0
    opportunities_created: int = 0
    opportunities_deduplicated: int = 0

    # Matching
    opportunities_scored: int = 0
    high_match_count: int = 0  # >= min_match_score

    # Planning
    summer_2027_count: int = 0
    now_count: int = 0
    upcoming_count: int = 0
    future_count: int = 0
    unknown_count: int = 0

    # Outreach
    drafts_created: int = 0

    # Follow-ups
    followups_marked_due: int = 0

    # Actions
    actions_generated: int = 0

    # Notifications
    notifications_generated: int = 0

    # Errors
    errors: list[str] = field(default_factory=list)

    # Dry run flag
    dry_run: bool = False

    def complete(self) -> None:
        """Mark the run as completed."""
        self.status = RunStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        """Mark the run as failed."""
        self.status = RunStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.errors.append(error)

    def duration_seconds(self) -> float | None:
        """Return the run duration in seconds, or None if not completed."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        """Serialize to a dict for API responses."""
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "trigger": self.trigger.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds(),
            "dry_run": self.dry_run,
            "sources_attempted": self.sources_attempted,
            "sources_succeeded": self.sources_succeeded,
            "sources_failed": self.sources_failed,
            "source_results": [
                {
                    "source_name": sr.source_name,
                    "raw_count": sr.raw_count,
                    "ingested": sr.ingested,
                    "duplicates_skipped": sr.duplicates_skipped,
                    "companies_created": sr.companies_created,
                    "success": sr.success,
                    "errors": sr.errors,
                }
                for sr in self.source_results
            ],
            "opportunities_seen": self.opportunities_seen,
            "opportunities_created": self.opportunities_created,
            "opportunities_deduplicated": self.opportunities_deduplicated,
            "opportunities_scored": self.opportunities_scored,
            "high_match_count": self.high_match_count,
            "summer_2027_count": self.summer_2027_count,
            "now_count": self.now_count,
            "upcoming_count": self.upcoming_count,
            "future_count": self.future_count,
            "unknown_count": self.unknown_count,
            "drafts_created": self.drafts_created,
            "followups_marked_due": self.followups_marked_due,
            "actions_generated": self.actions_generated,
            "notifications_generated": self.notifications_generated,
            "errors": self.errors,
        }


@dataclass
class AutomationStatus:
    """Current status of the automation engine."""
    enabled: bool = False
    scheduler_active: bool = False
    scheduler_interval_minutes: int = 60
    last_run: AutomationRunResult | None = None
    next_run_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "scheduler_active": self.scheduler_active,
            "scheduler_interval_minutes": self.scheduler_interval_minutes,
            "last_run": self.last_run.to_dict() if self.last_run else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
        }
