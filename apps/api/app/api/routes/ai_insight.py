"""AI Insight API route — enriched matching intelligence.

GET /matching/profiles/{profile_id}/opportunities/{opportunity_id}/insight

Returns the deterministic match score plus optional AI-generated insight.
AI is optional — if unavailable, the deterministic result is returned
with ai_insight.available = False.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.schemas.ai_insight import OpportunityMatchInsightResponse, AIInsightSchema
from app.services.ai_insight import generate_insight

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/matching",
    tags=["matching", "ai"],
)


def _get_ai_provider():
    """Attempt to create the AI provider from configuration.

    Returns None if not configured — this is normal and expected.
    """
    try:
        from app.core.config import get_settings

        settings = get_settings()

        if not settings.ai_api_key:
            return None

        from app.ai.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            api_url=settings.ai_api_url,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            timeout=settings.ai_timeout,
        )
    except Exception as exc:
        logger.debug("AI provider not available: %s", exc)
        return None


@router.get(
    "/profiles/{profile_id}/opportunities/{opportunity_id}/insight",
    response_model=OpportunityMatchInsightResponse,
    summary="Get match insight with optional AI enrichment",
    description=(
        "Calculate a deterministic match score and optionally enrich it "
        "with AI-generated explanation, strengths, gaps, and recommendations. "
        "AI enrichment is optional — if not configured, the deterministic "
        "result is returned with ai_insight.available=False."
    ),
)
async def get_match_insight(
    profile_id: int,
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> OpportunityMatchInsightResponse:
    # Validate profile
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Validate opportunity
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    # Get AI provider (may be None)
    provider = _get_ai_provider()

    # Generate insight (AI is optional)
    ai_insight, match_result = await generate_insight(
        db, profile, opportunity, provider=provider,
    )

    # Get company name
    from app.models.company import Company

    company = db.get(Company, opportunity.company_id)
    company_name = company.name if company else None

    return OpportunityMatchInsightResponse(
        opportunity_id=opportunity.id,
        title=opportunity.title,
        company_name=company_name,
        opportunity_type=opportunity.type,
        location=None,
        source_url=opportunity.source_url,
        # Deterministic scores (source of truth)
        score=match_result.score,
        matched_skills=match_result.matched_skills,
        missing_skills=match_result.missing_skills,
        matched_signals=match_result.matched_signals,
        concerns=match_result.concerns,
        explanation=match_result.explanation,
        skill_overlap_score=match_result.skill_overlap_score,
        title_relevance_score=match_result.title_relevance_score,
        experience_relevance_score=match_result.experience_relevance_score,
        project_relevance_score=match_result.project_relevance_score,
        location_fit_score=match_result.location_fit_score,
        type_fit_score=match_result.type_fit_score,
        # AI enrichment
        ai_insight=AIInsightSchema(
            available=ai_insight.available,
            provider=ai_insight.provider,
            model=ai_insight.model,
            error=ai_insight.error,
            match_explanation=ai_insight.match_explanation,
            strengths=ai_insight.strengths,
            gaps=ai_insight.gaps,
            recommendations=ai_insight.recommendations,
            outreach_angles=ai_insight.outreach_angles,
            application_advice=ai_insight.application_advice,
        ),
    )
