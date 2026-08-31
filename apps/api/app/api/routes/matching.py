"""Matching API routes — match profiles against opportunities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.schemas.matching import MatchResultSchema, RankedOpportunitiesResponse
from app.services.matching import match_opportunity, rank_opportunities

router = APIRouter(
    prefix="/matching",
    tags=["matching"],
)


@router.get(
    "/profiles/{profile_id}/opportunities/{opportunity_id}",
    response_model=MatchResultSchema,
    summary="Match a profile against a specific opportunity",
    description=(
        "Calculate a deterministic, explainable match score (0–100) "
        "between a user profile and an opportunity."
    ),
)
def match_single(
    profile_id: int,
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> MatchResultSchema:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    result = match_opportunity(db, profile, opportunity)

    # Get company name for response
    from app.models.company import Company

    company = db.get(Company, opportunity.company_id)
    company_name = company.name if company else None

    return MatchResultSchema(
        opportunity_id=opportunity.id,
        title=opportunity.title,
        company_name=company_name,
        opportunity_type=opportunity.type,
        location=None,
        source_url=opportunity.source_url,
        score=result.score,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        matched_signals=result.matched_signals,
        concerns=result.concerns,
        explanation=result.explanation,
        skill_overlap_score=result.skill_overlap_score,
        title_relevance_score=result.title_relevance_score,
        experience_relevance_score=result.experience_relevance_score,
        project_relevance_score=result.project_relevance_score,
        location_fit_score=result.location_fit_score,
        type_fit_score=result.type_fit_score,
    )


@router.get(
    "/profiles/{profile_id}/ranked",
    response_model=RankedOpportunitiesResponse,
    summary="Rank all opportunities by match score for a profile",
    description=(
        "Calculate match scores for all opportunities against a profile "
        "and return them ranked by score (highest first)."
    ),
)
def rank_all(
    profile_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> RankedOpportunitiesResponse:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    results = rank_opportunities(db, profile)

    # Build response with company names
    from app.models.company import Company

    matches: list[MatchResultSchema] = []
    for result in results[:limit]:
        opp_id = getattr(result, "opportunity_id", 0)
        opp_title = getattr(result, "title", "")
        opp = db.get(Opportunity, opp_id)
        company_name = None
        location = None
        source_url = None
        if opp:
            company = db.get(Company, opp.company_id)
            company_name = company.name if company else None
            source_url = opp.source_url

        matches.append(
            MatchResultSchema(
                opportunity_id=opp_id,
                title=opp_title,
                company_name=company_name,
                opportunity_type=opp.type if opp else "OTHER",
                location=location,
                source_url=source_url,
                score=result.score,
                matched_skills=result.matched_skills,
                missing_skills=result.missing_skills,
                matched_signals=result.matched_signals,
                concerns=result.concerns,
                explanation=result.explanation,
                skill_overlap_score=result.skill_overlap_score,
                title_relevance_score=result.title_relevance_score,
                experience_relevance_score=result.experience_relevance_score,
                project_relevance_score=result.project_relevance_score,
                location_fit_score=result.location_fit_score,
                type_fit_score=result.type_fit_score,
            )
        )

    return RankedOpportunitiesResponse(
        profile_id=profile_id,
        total_opportunities=len(results),
        matches=matches,
    )
