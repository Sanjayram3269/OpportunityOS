"""Enhanced Planning API routes — campaign-aware planning and overview.

Extends the existing planning endpoints with:
- Enhanced planning data with application/outreach/campaign context
- Planning overview summary
- Campaign-specific planning data
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.planning_enhanced import (
    get_enhanced_planning_data,
    get_planning_overview_summary,
)

router = APIRouter(tags=["planning-enhanced"])


@router.get(
    "/opportunities/planning/overview",
    summary="Planning landscape overview",
    description=(
        "Returns a summary of the planning landscape: counts by horizon, "
        "application status, and overall metrics."
    ),
)
def planning_overview(db: Session = Depends(get_db)):
    """Planning overview summary with horizon and application distributions."""
    return get_planning_overview_summary(db)


@router.get(
    "/opportunities/planning/enriched",
    summary="Enriched planning data",
    description=(
        "Returns opportunities with planning horizon, application status, "
        "outreach status, follow-up status, and campaign membership."
    ),
)
def enriched_planning(
    horizon: str | None = Query(
        default=None,
        description="Filter by planning horizon",
    ),
    min_match_score: int | None = Query(
        default=None, ge=0, le=100,
        description="Minimum match score",
    ),
    type: str | None = Query(default=None, description="Filter by opportunity type"),
    status: str | None = Query(default=None, description="Filter by status"),
    priority: str | None = Query(default=None, description="Filter by priority"),
    campaign_id: int | None = Query(
        default=None,
        description="Filter to opportunities in a specific campaign",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Enriched planning data with full context."""
    results = get_enhanced_planning_data(
        db,
        horizon=horizon,
        min_match_score=min_match_score,
        opp_type=type,
        status=status,
        priority=priority,
        campaign_id=campaign_id,
        limit=limit,
    )

    return {
        "total": len(results),
        "opportunities": results,
    }
