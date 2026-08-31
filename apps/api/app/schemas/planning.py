"""Pydantic schemas for the Opportunity Planning API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlanningHorizonInfo(BaseModel):
    """Planning classification for a single opportunity."""

    opportunity_id: int
    title: str
    company_name: str | None = None
    opportunity_type: str
    status: str
    priority: str
    deadline: datetime | None = None
    match_score: int | None = None

    # Planning-specific fields (deterministic, derived from data)
    planning_horizon: str = Field(
        description="Time horizon: NOW, UPCOMING, SUMMER_2027, FUTURE, UNKNOWN",
    )
    planning_priority: int = Field(
        ge=0, le=100,
        description="Planning priority score (0-100). Higher = act sooner.",
    )
    planning_priority_reasons: list[str] = Field(default_factory=list)


class PlanningListResponse(BaseModel):
    """Response for the planning endpoint."""

    total: int
    opportunities: list[PlanningHorizonInfo]
