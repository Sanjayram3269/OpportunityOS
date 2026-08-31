"""Feature extraction — pulls structured signals from Profile and Opportunity.

This module is pure / deterministic — no database or network calls.
It takes ORM objects and returns plain data structures ready for scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.matching.normalizer import extract_skills_from_text, normalize_skill, normalize_skills
from app.models.opportunity import Opportunity
from app.models.profile import Profile


@dataclass
class ProfileFeatures:
    """Extracted signals from a user profile."""

    skills: set[str] = field(default_factory=set)
    project_technologies: set[str] = field(default_factory=set)
    project_descriptions: set[str] = field(default_factory=set)
    experience_titles: set[str] = field(default_factory=set)
    experience_descriptions: set[str] = field(default_factory=set)
    headline: str | None = None
    bio: str | None = None
    headline_skills: set[str] = field(default_factory=set)
    bio_skills: set[str] = field(default_factory=set)

    @property
    def all_skills(self) -> set[str]:
        """Union of all skill sources."""
        return (
            self.skills
            | self.project_technologies
            | self.headline_skills
            | self.bio_skills
        )

    @property
    def has_any_data(self) -> bool:
        """Whether the profile has any data useful for matching."""
        return bool(
            self.skills
            or self.project_technologies
            or self.experience_titles
            or self.headline
            or self.bio
        )


@dataclass
class OpportunityFeatures:
    """Extracted signals from an opportunity."""

    title: str
    type: str
    location: str | None = None
    description_skills: set[str] = field(default_factory=set)
    title_skills: set[str] = field(default_factory=set)
    metadata_skills: set[str] = field(default_factory=set)
    description: str | None = None
    company_name: str | None = None

    @property
    def all_skills(self) -> set[str]:
        """Union of all skill sources from the opportunity."""
        return self.description_skills | self.title_skills | self.metadata_skills


# ── Extraction functions ──────────────────────────────────────────────────


def extract_profile_features(
    profile: Profile,
    skills: list | None = None,
    projects: list | None = None,
    experiences: list | None = None,
) -> ProfileFeatures:
    """Extract matching-relevant features from a Profile.

    Args:
        profile: The Profile ORM object.
        skills: Optional list of Skill ORM objects (profile.skills if loaded).
        projects: Optional list of Project ORM objects (profile.projects if loaded).
        experiences: Optional list of Experience ORM objects (profile.experiences if loaded).
    """
    features = ProfileFeatures()

    # ── Skills from the skills table ───────────────────────────────
    if skills:
        features.skills = normalize_skills([s.name for s in skills])

    # ── Skills from projects ───────────────────────────────────────
    if projects:
        for project in projects:
            if project.technologies:
                techs = [t.strip() for t in project.technologies.split(",") if t.strip()]
                features.project_technologies |= normalize_skills(techs)
            if project.description:
                features.project_descriptions.add(project.description)
                features.project_technologies |= extract_skills_from_text(project.description)

    # ── Skills from experience ─────────────────────────────────────
    if experiences:
        for exp in experiences:
            features.experience_titles.add(exp.title.lower())
            if exp.description:
                features.experience_descriptions.add(exp.description)

    # ── Headline and bio ──────────────────────────────────────────
    if profile.headline:
        features.headline = profile.headline
        features.headline_skills = extract_skills_from_text(profile.headline)

    if profile.bio:
        features.bio = profile.bio
        features.bio_skills = extract_skills_from_text(profile.bio)

    return features


def extract_opportunity_features(
    opportunity: Opportunity,
    company_name: str | None = None,
) -> OpportunityFeatures:
    """Extract matching-relevant features from an Opportunity.

    Args:
        opportunity: The Opportunity ORM object.
        company_name: Optional company name (fetched separately if needed).
    """
    features = OpportunityFeatures(
        title=opportunity.title,
        type=opportunity.type,
        location=None,
        description=opportunity.description,
        company_name=company_name,
    )

    # ── Skills from description ────────────────────────────────────
    if opportunity.description:
        features.description_skills = extract_skills_from_text(opportunity.description)

    # ── Skills from title ──────────────────────────────────────────
    features.title_skills = extract_skills_from_text(opportunity.title)

    # ── Skills from evidence/metadata ──────────────────────────────
    # Evidence content might contain tags, categories, etc.
    if hasattr(opportunity, "evidence") and opportunity.evidence:
        for ev in opportunity.evidence:
            if ev.evidence_type in ("tags", "categories", "skills"):
                tags = [t.strip() for t in ev.content.split(",") if t.strip()]
                features.metadata_skills |= normalize_skills(tags)

    return features
