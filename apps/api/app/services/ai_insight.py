"""AI insight service — bridges deterministic matching with AI enrichment.

The service:
1. Runs deterministic matching
2. Builds structured context from profile + opportunity + match result
3. Calls the AI provider (if available)
4. Returns AIInsight with deterministic score preserved

AI failures never crash the service — they return unavailable insight.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai.base import AIInsight, AIProvider, AIProviderError, AIPermissionError, AITimeoutError
from app.ai.prompts import (
    build_match_result_summary,
    build_opportunity_summary,
    build_profile_summary,
)
from app.matching.extractor import extract_opportunity_features, extract_profile_features
from app.matching.scorer import score_match
from app.models.company import Company
from app.models.experience import Experience
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill

logger = logging.getLogger(__name__)


def build_context(
    db: Session,
    profile: Profile,
    opportunity: Opportunity,
) -> dict[str, Any]:
    """Build the structured context for AI insight generation.

    This extracts all relevant data without calling AI.
    """
    # Load related collections
    skills = db.query(Skill).filter(Skill.profile_id == profile.id).all()
    projects = db.query(Project).filter(Project.profile_id == profile.id).all()
    experiences = db.query(Experience).filter(Experience.profile_id == profile.id).all()

    # Extract features
    profile_features = extract_profile_features(
        profile, skills=skills, projects=projects, experiences=experiences,
    )
    company = db.get(Company, opportunity.company_id)
    company_name = company.name if company else None
    opp_features = extract_opportunity_features(opportunity, company_name=company_name)

    # Score
    match_result = score_match(profile_features, opp_features)

    # Build summaries
    profile_summary = build_profile_summary(
        profile_name=profile.name,
        headline=profile.headline,
        bio=profile.bio,
        skills=list(profile_features.all_skills),
        project_technologies=list(profile_features.project_technologies),
        project_descriptions=list(profile_features.project_descriptions),
        experience_titles=list(profile_features.experience_titles),
        experience_descriptions=list(profile_features.experience_descriptions),
    )

    opportunity_summary = build_opportunity_summary(
        title=opportunity.title,
        company_name=company_name,
        description=opportunity.description,
        location=opp_features.location,
        opp_type=opportunity.type,
        deadline=opportunity.deadline.isoformat() if opportunity.deadline else None,
        source_url=opportunity.source_url,
    )

    match_result_summary = build_match_result_summary(
        score=match_result.score,
        matched_skills=match_result.matched_skills,
        missing_skills=match_result.missing_skills,
        matched_signals=match_result.matched_signals,
        concerns=match_result.concerns,
        explanation=match_result.explanation,
        component_scores={
            "skill_overlap": match_result.skill_overlap_score,
            "title_relevance": match_result.title_relevance_score,
            "experience_relevance": match_result.experience_relevance_score,
            "project_relevance": match_result.project_relevance_score,
            "location_fit": match_result.location_fit_score,
            "type_fit": match_result.type_fit_score,
        },
    )

    return {
        "profile_summary": profile_summary,
        "opportunity_summary": opportunity_summary,
        "match_result_summary": match_result_summary,
        "match_result": match_result,
    }


async def generate_insight(
    db: Session,
    profile: Profile,
    opportunity: Opportunity,
    provider: AIProvider | None = None,
) -> tuple[AIInsight, Any]:
    """Generate AI insight for a profile-opportunity match.

    Returns:
        A tuple of (AIInsight, MatchResult). The MatchResult is always
        valid regardless of AI availability.

    The AI provider is optional. If None or unavailable, an unavailable
    insight is returned with the deterministic match result.
    """
    # Always run deterministic matching first
    context = build_context(db, profile, opportunity)
    match_result = context["match_result"]

    # If no provider, return immediately
    if provider is None:
        return AIInsight.unavailable("No AI provider configured"), match_result

    # Build the AI request context
    ai_context = {
        "profile_summary": context["profile_summary"],
        "opportunity_summary": context["opportunity_summary"],
        "match_result": context["match_result_summary"],
    }

    try:
        raw_response = await provider.generate_insight(ai_context)
        raw_response["provider"] = provider.provider_name
        raw_response["model"] = provider.model_name
        insight = AIInsight.from_dict(raw_response)
        insight.available = True
        return insight, match_result

    except AIPermissionError as exc:
        logger.warning("AI provider not configured: %s", exc)
        return AIInsight.unavailable(str(exc)), match_result

    except AITimeoutError as exc:
        logger.warning("AI provider timed out: %s", exc)
        return AIInsight.unavailable(f"Provider timeout: {exc}"), match_result

    except AIProviderError as exc:
        logger.error("AI provider error: %s", exc)
        return AIInsight.unavailable(f"Provider error: {exc}"), match_result

    except Exception as exc:
        logger.error("Unexpected AI error: %s", exc)
        return AIInsight.unavailable(f"Unexpected error: {exc}"), match_result
