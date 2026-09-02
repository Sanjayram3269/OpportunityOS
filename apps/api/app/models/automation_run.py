"""AutomationRun model — persistent record of automation cycle executions.

Records what the automation system did during each run so operational
history is observable across restarts.

Does NOT store secrets, raw API payloads, or stack traces.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AutomationRun(Base):
    """A persisted record of one automation cycle execution."""

    __tablename__ = "automation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    run_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
    )

    trigger: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MANUAL",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="RUNNING",
    )

    dry_run: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # Discovery counts
    sources_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sources_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_deduplicated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Planning counts
    summer_2027_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    now_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upcoming_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    future_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Action & notification counts
    actions_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notifications_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    followups_marked_due: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Error summary (human-readable, no stack traces)
    error_summary: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# Indexes for efficient querying
Index("ix_automation_runs_started_at", AutomationRun.started_at)
Index("ix_automation_runs_status", AutomationRun.status)
Index("ix_automation_runs_trigger", AutomationRun.trigger)
