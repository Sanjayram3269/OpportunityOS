"""Matching service — orchestrates feature extraction and scoring.

This module bridges the database layer (ORM models) and the pure
matching engine (extractor + scorer).  All database access happens here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching.extractor import (
    OpportunityFeatures,
    ProfileFeatures,
    extract_opportunity_features,
    extract_profile_features,
)
from app.matching.scorer import MatchResult, score_match
from app.models.company import Company
from app.models.experience import Experience
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill


def match_opportunity(
    db: Session,
    profile: Profile,
    opportunity: Opportunity,
) -> MatchResult:
    """Calculate a match score between a profile and an opportunity.

    This is the core matching function.  It:
      1. Extracts features from both profile and opportunity
      2. Runs the deterministic scorer
      3. Returns an explainable MatchResult
    """
    # Load related collections
    skills = db.query(Skill).filter(Skill.profile_id == profile.id).all()
    projects = db.query(Project).filter(Project.profile_id == profile.id).all()
    experiences = db.query(Experience).filter(Experience.profile_id == profile.id).all()

    # Extract profile features
    profile_features = extract_profile_features(
        profile, skills=skills, projects=projects, experiences=experiences,
    )

    # Get company name for context
    company = db.get(Company, opportunity.company_id)
    company_name = company.name if company else None

    # Extract opportunity features
    opp_features = extract_opportunity_features(opportunity, company_name=company_name)

    # Score
    return score_match(profile_features, opp_features)


def rank_opportunities(
    db: Session,
    profile: Profile,
    opportunities: list[Opportunity] | None = None,
) -> list[MatchResult]:
    """Rank all opportunities (or a provided list) against a profile.

    Returns results sorted by score descending.
    """
    if opportunities is None:
        opportunities = db.query(Opportunity).all()

    results: list[MatchResult] = []
    for opp in opportunities:
        result = match_opportunity(db, profile, opp)
        # Attach opportunity metadata to the result for the API layer
        result.opportunity_id = opp.id  # type: ignore[attr-defined]
        result.title = opp.title  # type: ignore[attr-defined]
        results.append(result)

    # Sort by score descending, then by opportunity_id for determinism
    results.sort(key=lambda r: (-r.score, getattr(r, "opportunity_id", 0)))  # type: ignore[arg-type]

    return results
