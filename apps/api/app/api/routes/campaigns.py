"""Campaign API routes — CRUD, lifecycle, membership, and summary.

Endpoints:
    POST   /campaigns                              → Create campaign
    GET    /campaigns                              → List campaigns
    GET    /campaigns/{id}                         → Get campaign
    PATCH  /campaigns/{id}                         → Update campaign
    POST   /campaigns/{id}/activate                → Activate
    POST   /campaigns/{id}/pause                   → Pause
    POST   /campaigns/{id}/complete                → Complete
    POST   /campaigns/{id}/archive                 → Archive
    POST   /campaigns/{id}/opportunities/{opp_id}  → Add opportunity
    DELETE /campaigns/{id}/opportunities/{opp_id}  → Remove opportunity
    GET    /campaigns/{id}/opportunities           → List opportunities
    GET    /campaigns/{id}/summary                 → Campaign summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignOpportunityResponse,
    CampaignResponse,
    CampaignStateTransitionResponse,
    CampaignSummaryResponse,
    CampaignUpdateRequest,
)
from app.services.campaign import (
    ACTIVE,
    ARCHIVED,
    COMPLETED,
    DRAFT,
    PAUSED,
    CampaignStateError,
    activate_campaign,
    add_opportunity_to_campaign,
    archive_campaign,
    complete_campaign,
    create_campaign,
    get_campaign,
    get_campaign_summary,
    list_campaign_opportunities,
    list_campaigns,
    pause_campaign,
    remove_opportunity_from_campaign,
    update_campaign,
)

router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns"],
)


# ── CRUD ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a campaign",
)
def create_new_campaign(
    request: CampaignCreateRequest,
    db: Session = Depends(get_db),
) -> CampaignResponse:
    campaign = create_campaign(
        db,
        name=request.name,
        type=request.type,
        description=request.description,
        target_description=request.target_description,
    )
    return CampaignResponse.model_validate(campaign)


@router.get(
    "",
    response_model=CampaignListResponse,
    summary="List campaigns",
)
def list_all_campaigns(
    status_filter: str | None = Query(default=None, alias="status"),
    type_filter: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CampaignListResponse:
    campaigns = list_campaigns(db, status=status_filter, type=type_filter, limit=limit)
    return CampaignListResponse(
        total=len(campaigns),
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get a campaign",
)
def get_single_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
) -> CampaignResponse:
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.patch(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Update a campaign",
)
def update_single_campaign(
    campaign_id: int,
    request: CampaignUpdateRequest,
    db: Session = Depends(get_db),
) -> CampaignResponse:
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        updated = update_campaign(
            db,
            campaign,
            name=request.name,
            type=request.type,
            description=request.description,
            target_description=request.target_description,
        )
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return CampaignResponse.model_validate(updated)


# ── Lifecycle ────────────────────────────────────────────────────────────


def _transition(db, campaign_id, action_fn, action_name):
    """Helper for state transition endpoints."""
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    previous = campaign.status
    try:
        updated = action_fn(db, campaign)
    except CampaignStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return CampaignStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message=f"Campaign {action_name}",
    )


@router.post("/{campaign_id}/activate", response_model=CampaignStateTransitionResponse)
def activate_single_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, activate_campaign, "activated")


@router.post("/{campaign_id}/pause", response_model=CampaignStateTransitionResponse)
def pause_single_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, pause_campaign, "paused")


@router.post("/{campaign_id}/complete", response_model=CampaignStateTransitionResponse)
def complete_single_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, complete_campaign, "completed")


@router.post("/{campaign_id}/archive", response_model=CampaignStateTransitionResponse)
def archive_single_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _transition(db, campaign_id, archive_campaign, "archived")


# ── Membership ───────────────────────────────────────────────────────────


@router.post(
    "/{campaign_id}/opportunities/{opportunity_id}",
    response_model=CampaignOpportunityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add opportunity to campaign",
)
def add_opp_to_campaign(
    campaign_id: int,
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> CampaignOpportunityResponse:
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        add_opportunity_to_campaign(db, campaign, opportunity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return CampaignOpportunityResponse(
        campaign_id=campaign_id,
        opportunity_id=opportunity_id,
        message="Opportunity added to campaign",
    )


@router.delete(
    "/{campaign_id}/opportunities/{opportunity_id}",
    response_model=CampaignOpportunityResponse,
    summary="Remove opportunity from campaign",
)
def remove_opp_from_campaign(
    campaign_id: int,
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> CampaignOpportunityResponse:
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    removed = remove_opportunity_from_campaign(db, campaign, opportunity_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail="Opportunity not in this campaign",
        )

    return CampaignOpportunityResponse(
        campaign_id=campaign_id,
        opportunity_id=opportunity_id,
        message="Opportunity removed from campaign",
    )


@router.get(
    "/{campaign_id}/opportunities",
    summary="List opportunities in a campaign",
)
def list_campaign_opps(
    campaign_id: int,
    db: Session = Depends(get_db),
):
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    opps = list_campaign_opportunities(db, campaign)
    return {
        "campaign_id": campaign_id,
        "total": len(opps),
        "opportunities": [
            {
                "id": o.id,
                "title": o.title,
                "type": o.type,
                "status": o.status,
                "match_score": o.match_score,
                "deadline": o.deadline.isoformat() if o.deadline else None,
            }
            for o in opps
        ],
    }


# ── Summary ──────────────────────────────────────────────────────────────


@router.get(
    "/{campaign_id}/summary",
    response_model=CampaignSummaryResponse,
    summary="Campaign activity summary",
)
def get_single_campaign_summary(
    campaign_id: int,
    db: Session = Depends(get_db),
) -> CampaignSummaryResponse:
    campaign = get_campaign(db, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    summary = get_campaign_summary(db, campaign)
    return CampaignSummaryResponse(**summary)
