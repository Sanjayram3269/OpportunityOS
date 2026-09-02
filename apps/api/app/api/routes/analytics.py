"""Analytics deep dive + Application timeline API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.analytics_deep import get_analytics_overview

router = APIRouter()


# ── Analytics ─────────────────────────────────────────────────────────────

@router.get("/analytics/overview")
def analytics_overview(
    start_date: str | None = Query(None, description="ISO date string"),
    end_date: str | None = Query(None, description="ISO date string"),
    db: Session = Depends(get_db),
):
    """Comprehensive analytics overview with optional date filtering.

    Supports:
    - trends (current vs previous period)
    - velocity (stage durations)
    - conversion (stage-by-stage)
    - source analytics (per company)
    - campaign analytics
    - type analytics
    - match bucket analytics
    - Summer 2027 analytics
    """
    now = datetime.now(timezone.utc)

    sd = None
    ed = None
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            if sd.tzinfo is None:
                sd = sd.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            if ed.tzinfo is None:
                ed = ed.replace(tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    if sd and ed and sd > ed:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    return get_analytics_overview(db, start_date=sd, end_date=ed)
