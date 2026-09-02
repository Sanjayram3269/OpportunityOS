"""Enhanced Campaign API routes — planning intelligence and action summary.

Extends the existing campaign endpoints with:
- Enhanced campaign summary with application/action breakdowns
- Campaign planning data with horizon classification
- Campaign action summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.campaign import get_campaign
from app.services.campaign_enhanced import (
    get_campaign_action_summary,
    get_campaign_planning_data,
    get_enhanced_campaign_summary,
)

router = APIRouter(tags=["campaigns-enhanced"])


@router.get(
    "/campaigns/{campaign_id}/enhanced-summary",
    summary="Enhanced campaign summary",
    description=(
        "Returns comprehensive campaign summary with application status breakdown, "
        "action status, planning horizon distribution, and follow-up status."
    ),
)
def enhanced_campaign_summary(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    """Enhanced campaign summary with application and action context."""
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return get_enhanced_campaign_summary(db, campaign)


@router.get(
    "/campaigns/{campaign_id}/planning",
    summary="Campaign planning data",
    description=(
        "Returns planning data for opportunities in this campaign, "
        "with horizon classification and application status."
    ),
)
def campaign_planning(
    campaign_id: int,
    horizon: str | None = Query(
        default=None,
        description="Filter by planning horizon",
    ),
    min_match_score: int | None = Query(
        default=None, ge=0, le=100,
        description="Minimum match score",
    ),
    db: Session = Depends(get_db),
):
    """Planning data for opportunities in a specific campaign."""
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    results = get_campaign_planning_data(
        db,
        campaign,
        horizon=horizon,
        min_match_score=min_match_score,
    )

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "total": len(results),
        "opportunities": results,
    }


@router.get(
    "/campaigns/{campaign_id}/action-summary",
    summary="Campaign action summary",
    description=(
        "Returns counts of open actions for opportunities in this campaign, "
        "broken down by priority and type."
    ),
)
def campaign_action_summary(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    """Action summary for opportunities in a specific campaign."""
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return get_campaign_action_summary(db, campaign)
