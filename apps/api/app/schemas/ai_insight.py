"""Pydantic schemas for the AI insight API response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AIInsightSchema(BaseModel):
    """AI-generated intelligence for an opportunity match."""

    available: bool = Field(
        description="Whether AI insight was successfully generated",
    )
    provider: str = Field(
        default="",
        description="AI provider name (e.g. 'huggingface', 'openrouter')",
    )
    model: str = Field(
        default="",
        description="Model used for generation",
    )
    error: str | None = Field(
        default=None,
        description="Error message if AI is unavailable",
    )

    match_explanation: str = Field(
        default="",
        description="Why this opportunity matches the profile",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Profile strengths aligned with this opportunity",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Missing skills or requirements",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="What to emphasize or improve",
    )
    outreach_angles: list[str] = Field(
        default_factory=list,
        description="Genuine points for a personalized message",
    )
    application_advice: str = Field(
        default="",
        description="Concise advice specific to this opportunity",
    )


class OpportunityMatchInsightResponse(BaseModel):
    """Full response for the insight endpoint.

    Includes both the deterministic match result and AI insight.
    The score is ALWAYS from the deterministic engine.
    """

    opportunity_id: int
    title: str
    company_name: str | None = None
    opportunity_type: str
    location: str | None = None
    source_url: str | None = None

    # Deterministic match (source of truth for the score)
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

    # AI enrichment
    ai_insight: AIInsightSchema
