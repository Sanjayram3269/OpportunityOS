"""Pydantic schemas for the matching API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MatchResultSchema(BaseModel):
    """Schema for a single opportunity match result."""

    opportunity_id: int
    title: str
    company_name: str | None = None
    opportunity_type: str
    location: str | None = None
    source_url: str | None = None

    score: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    matched_signals: list[str]
    concerns: list[str]
    explanation: str

    # Component scores
    skill_overlap_score: int
    title_relevance_score: int
    experience_relevance_score: int
    project_relevance_score: int
    location_fit_score: int
    type_fit_score: int


class RankedOpportunitiesResponse(BaseModel):
    """Response for the ranked opportunities endpoint."""

    profile_id: int
    total_opportunities: int
    matches: list[MatchResultSchema]
