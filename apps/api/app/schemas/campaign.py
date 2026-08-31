"""Pydantic schemas for the Campaign Management API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ──────────────────────────────────────────────────────


class CampaignCreateRequest(BaseModel):
    """Request to create a new campaign."""

    name: str = Field(min_length=1, max_length=200)
    type: str = Field(
        description="Campaign type (e.g. INTERNSHIP, FULL_TIME, STARTUP, RESEARCH)",
    )
    description: str | None = None
    target_description: str | None = None


class CampaignUpdateRequest(BaseModel):
    """Request to update a campaign."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = None
    description: str | None = None
    target_description: str | None = None


# ── Response schemas ─────────────────────────────────────────────────────


class CampaignResponse(BaseModel):
    """Response for a single campaign."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    description: str | None = None
    target_description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    """Response for listing campaigns."""

    total: int
    campaigns: list[CampaignResponse]


class CampaignStateTransitionResponse(BaseModel):
    """Response after a state transition."""

    id: int
    previous_status: str
    new_status: str
    message: str


class CampaignOpportunityResponse(BaseModel):
    """Response after adding/removing an opportunity."""

    campaign_id: int
    opportunity_id: int
    message: str


class CampaignSummaryResponse(BaseModel):
    """Deterministic summary of a campaign's activity."""

    campaign_id: int
    campaign_name: str
    total_opportunities: int
    average_match_score: float | None = None
    high_match_count: int = 0
    drafts_count: int = 0
    pending_approval_count: int = 0
    approved_count: int = 0
    sent_count: int = 0
    followups_pending: int = 0
    followups_completed: int = 0
    followups_cancelled: int = 0
