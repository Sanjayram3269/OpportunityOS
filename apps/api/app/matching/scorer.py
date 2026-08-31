"""Deterministic scoring engine — calculates explainable match scores.

The same Profile + Opportunity always produces the same MatchResult.
No external calls, no randomness, no LLM.

Scoring components (total = 100):
  - skill_overlap:       0–40  (most important signal)
  - title_relevance:     0–20
  - experience_relevance: 0–15
  - project_relevance:   0–10
  - location_fit:        0–10
  - type_fit:            0–5
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.matching.extractor import OpportunityFeatures, ProfileFeatures
from app.matching.normalizer import normalize_skill

# ── MatchResult ───────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    """Explainable result of matching a Profile against an Opportunity."""

    score: int  # 0–100
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    matched_signals: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    explanation: str = ""

    # Component scores for transparency
    skill_overlap_score: int = 0
    title_relevance_score: int = 0
    experience_relevance_score: int = 0
    project_relevance_score: int = 0
    location_fit_score: int = 0
    type_fit_score: int = 0


# ── Scoring constants ─────────────────────────────────────────────────────

# Maximum points per component
_MAX_SKILL = 40
_MAX_TITLE = 20
_MAX_EXPERIENCE = 15
_MAX_PROJECT = 10
_MAX_LOCATION = 10
_MAX_TYPE = 5

# Skill overlap thresholds (number of matched skills → points)
_SKILL_THRESHOLDS: list[tuple[int, int]] = [
    (8, 40),  # 8+ skills → full marks
    (6, 34),
    (5, 30),
    (4, 25),
    (3, 20),
    (2, 14),
    (1, 8),
    (0, 0),
]

# ── Location matching ─────────────────────────────────────────────────────

_REMOTE_KEYWORDS = {"remote", "worldwide", "anywhere", "global", "distributed"}


def _normalize_location(loc: str | None) -> str:
    """Normalize a location string for comparison."""
    if not loc:
        return ""
    return loc.lower().strip()


def _location_compatible(profile_loc: str | None, opp_loc: str | None) -> int:
    """Return a location fit score (0–10).

    Scoring:
      - Remote/Worldwide opportunity → 10 (always compatible)
      - No opportunity location → 8 (assumes flexible)
      - Exact city/country match → 10
      - Partial match (e.g. both contain "India") → 7
      - No profile location + non-remote → 5 (unknown, not penalized)
      - Mismatch → 2 (not zero — location can often be negotiated)
    """
    opp_norm = _normalize_location(opp_loc)
    prof_norm = _normalize_location(profile_loc)

    # Remote/Worldwide opportunities are always compatible
    if any(kw in opp_norm for kw in _REMOTE_KEYWORDS):
        return 10

    # No opportunity location → assume flexible
    if not opp_norm:
        return 8

    # No profile location → don't penalize
    if not prof_norm:
        return 5

    # Exact match
    if prof_norm == opp_norm:
        return 10

    # Containment check (e.g. "Bengaluru, India" contains "India")
    if prof_norm in opp_norm or opp_norm in prof_norm:
        return 9

    # Country-level match (both contain same country keyword)
    prof_words = set(prof_norm.replace(",", " ").split())
    opp_words = set(opp_norm.replace(",", " ").split())
    common = prof_words & opp_words
    # Filter out very short words
    common = {w for w in common if len(w) > 2}
    if common:
        return 7

    # Mismatch — still some possibility
    return 2


# ── Opportunity type matching ─────────────────────────────────────────────

_TYPE_COMPATIBILITY: dict[str, list[str]] = {
    "INTERNSHIP": ["INTERNSHIP"],
    "FULL_TIME": ["FULL_TIME", "INTERNSHIP"],
    "PART_TIME": ["PART_TIME", "FREELANCE", "CONTRACT"],
    "CONTRACT": ["CONTRACT", "FREELANCE"],
    "FREELANCE": ["FREELANCE", "CONTRACT"],
    "RESEARCH": ["RESEARCH", "INTERNSHIP"],
    "HACKATHON": ["HACKATHON"],
    "STARTUP": ["STARTUP", "FULL_TIME", "FREELANCE"],
    "VOLUNTEER": ["VOLUNTEER"],
    "OTHER": [],
}


def _type_fit_score(profile_type_pref: str | None, opp_type: str) -> int:
    """Return a type fit score (0–5).

    Without explicit profile preferences, we give a moderate base score
    and bonus for universally common types.
    """
    opp_upper = opp_type.upper() if opp_type else "OTHER"

    # Without explicit preference, give a reasonable base
    if not profile_type_pref:
        # Internships and full-time are broadly relevant
        if opp_upper in ("FULL_TIME", "INTERNSHIP", "RESEARCH", "HACKATHON"):
            return 4
        return 3

    pref_upper = profile_type_pref.upper()
    compatible = _TYPE_COMPATIBILITY.get(pref_upper, [])
    if opp_upper == pref_upper or opp_upper in compatible:
        return 5
    return 2


# ── Title relevance ───────────────────────────────────────────────────────

_TITLE_KEYWORD_MATCHES: list[tuple[str, list[str]]] = [
    ("engineer", ["engineer", "developer", "sde", "software"]),
    ("developer", ["developer", "engineer", "sde", "software"]),
    ("intern", ["intern", "internship"]),
    ("research", ["research", "scientist", "researcher"]),
    ("data", ["data", "analytics", "analyst"]),
    ("ml", ["ml", "machine learning", "ai", "artificial intelligence"]),
    ("ai", ["ai", "ml", "machine learning", "artificial intelligence"]),
    ("frontend", ["frontend", "front-end", "ui", "react", "vue"]),
    ("backend", ["backend", "back-end", "server", "api"]),
    ("fullstack", ["fullstack", "full-stack", "full stack"]),
    ("devops", ["devops", "infrastructure", "sre", "platform"]),
    ("cloud", ["cloud", "aws", "gcp", "azure"]),
]


def _title_relevance_score(
    profile_features: ProfileFeatures,
    opp_features: OpportunityFeatures,
) -> int:
    """Return a title relevance score (0–20).

    Checks alignment between:
      - Opportunity title ↔ Profile headline
      - Opportunity title ↔ Profile experience titles
    """
    opp_title_lower = opp_features.title.lower()
    score = 0

    # Check headline alignment
    if profile_features.headline:
        headline_lower = profile_features.headline.lower()
        # Direct word overlap between headline and opportunity title
        opp_words = set(opp_title_lower.split())
        headline_words = set(headline_lower.split())
        overlap = opp_words & headline_words
        # Filter out very common words
        stopwords = {"a", "an", "the", "in", "at", "for", "of", "and", "or", "to", "with", "is", "are"}
        overlap -= stopwords
        if overlap:
            score += min(10, len(overlap) * 5)

    # Check experience title alignment
    if profile_features.experience_titles:
        for exp_title in profile_features.experience_titles:
            # Check if any experience title shares keywords with opportunity title
            exp_words = set(exp_title.split())
            opp_words = set(opp_title_lower.split())
            overlap = exp_words & opp_words
            overlap -= {"a", "an", "the", "in", "at", "for", "of", "and", "or", "to", "with", "is", "are"}
            if overlap:
                score += min(5, len(overlap) * 3)

    # Keyword-based relevance
    for keyword, related in _TITLE_KEYWORD_MATCHES:
        if keyword in opp_title_lower:
            # Check if profile has any related signal
            all_profile_text = " ".join([
                profile_features.headline or "",
                " ".join(profile_features.experience_titles),
            ]).lower()
            if any(rel in all_profile_text for rel in related):
                score += 3

    return min(_MAX_TITLE, score)


# ── Experience relevance ──────────────────────────────────────────────────


def _experience_relevance_score(
    profile_features: ProfileFeatures,
    opp_features: OpportunityFeatures,
) -> int:
    """Return an experience relevance score (0–15).

    Checks if the opportunity description mentions skills/experiences
    the candidate has demonstrated.
    """
    if not profile_features.experience_descriptions:
        return 0

    score = 0
    opp_text = (opp_features.description or "").lower()

    for exp_desc in profile_features.experience_descriptions:
        exp_lower = exp_desc.lower()
        # Check if any words from experience description appear in opportunity
        exp_words = set(exp_lower.split())
        opp_words = set(opp_text.split())
        overlap = exp_words & opp_words
        # Filter stopwords
        stopwords = {"a", "an", "the", "in", "at", "for", "of", "and", "or", "to", "with", "is", "are", "we", "our", "this", "that"}
        overlap -= stopwords
        if len(overlap) >= 3:
            score += min(5, len(overlap))

    return min(_MAX_EXPERIENCE, score)


# ── Project relevance ─────────────────────────────────────────────────────


def _project_relevance_score(
    profile_features: ProfileFeatures,
    opp_features: OpportunityFeatures,
) -> int:
    """Return a project relevance score (0–10).

    Checks technology overlap between projects and opportunity.
    """
    if not profile_features.project_technologies:
        return 0

    opp_skills = opp_features.all_skills
    if not opp_skills:
        return 0

    overlap = profile_features.project_technologies & opp_skills
    if not overlap:
        return 0

    # Proportional scoring
    ratio = len(overlap) / max(len(opp_skills), 1)
    return min(_MAX_PROJECT, int(ratio * _MAX_PROJECT * 2))  # generous


# ── Main scoring function ─────────────────────────────────────────────────


def score_match(
    profile_features: ProfileFeatures,
    opp_features: OpportunityFeatures,
    profile_type_preference: str | None = None,
) -> MatchResult:
    """Calculate a deterministic, explainable match score.

    Args:
        profile_features: Extracted features from the user's profile.
        opp_features: Extracted features from the opportunity.
        profile_type_preference: Optional preferred opportunity type.

    Returns:
        A MatchResult with score (0–100), signals, and explanation.
    """
    result = MatchResult(score=0)

    # ── Skill overlap (0–40) ──────────────────────────────────────
    profile_skills = profile_features.all_skills
    opp_skills = opp_features.all_skills
    matched = sorted(profile_skills & opp_skills)

    # Find "missing" skills — skills the opportunity mentions but profile lacks
    missing = sorted(opp_skills - profile_skills)

    # Score based on number of matches
    skill_score = 0
    for threshold, points in _SKILL_THRESHOLDS:
        if len(matched) >= threshold:
            skill_score = points
            break

    result.skill_overlap_score = skill_score
    result.matched_skills = matched
    result.missing_skills = missing

    if matched:
        result.matched_signals.append(
            f"Skills match: {len(matched)} shared ({', '.join(matched[:5])}{'...' if len(matched) > 5 else ''})"
        )
    if missing:
        result.concerns.append(
            f"Missing skills: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}"
        )

    # ── Title relevance (0–20) ────────────────────────────────────
    title_score = _title_relevance_score(profile_features, opp_features)
    result.title_relevance_score = title_score
    if title_score >= 15:
        result.matched_signals.append("Strong title alignment with your background")
    elif title_score >= 8:
        result.matched_signals.append("Moderate title alignment")

    # ── Experience relevance (0–15) ───────────────────────────────
    exp_score = _experience_relevance_score(profile_features, opp_features)
    result.experience_relevance_score = exp_score
    if exp_score >= 10:
        result.matched_signals.append("Your experience is highly relevant")
    elif exp_score >= 5:
        result.matched_signals.append("Some experience overlap detected")

    # ── Project relevance (0–10) ──────────────────────────────────
    proj_score = _project_relevance_score(profile_features, opp_features)
    result.project_relevance_score = proj_score
    if proj_score >= 7:
        result.matched_signals.append("Your projects demonstrate relevant technologies")

    # ── Location fit (0–10) ───────────────────────────────────────
    loc_score = _location_compatible(None, opp_features.location)
    result.location_fit_score = loc_score
    if loc_score >= 8:
        result.matched_signals.append(f"Location compatible: {opp_features.location or 'flexible'}")
    elif loc_score <= 3:
        result.concerns.append(f"Location may not align: {opp_features.location}")

    # ── Type fit (0–5) ────────────────────────────────────────────
    type_score = _type_fit_score(profile_type_preference, opp_features.type)
    result.type_fit_score = type_score

    # ── Total score ───────────────────────────────────────────────
    result.score = min(100, (
        skill_score
        + title_score
        + exp_score
        + proj_score
        + loc_score
        + type_score
    ))

    # ── Generate explanation ──────────────────────────────────────
    result.explanation = _build_explanation(result, profile_features, opp_features)

    return result


def _build_explanation(
    result: MatchResult,
    profile_features: ProfileFeatures,
    opp_features: OpportunityFeatures,
) -> str:
    """Build a human-readable explanation of the match score."""
    parts = []

    if result.score >= 75:
        parts.append("Strong match")
    elif result.score >= 50:
        parts.append("Good match")
    elif result.score >= 25:
        parts.append("Moderate match")
    else:
        parts.append("Weak match")

    if result.matched_skills:
        parts.append(
            f"with {len(result.matched_skills)} shared skills"
        )

    if result.title_relevance_score >= 10:
        parts.append("and strong role alignment")

    if result.concerns:
        parts.append(f"({len(result.concerns)} concern{'s' if len(result.concerns) > 1 else ''})")

    return ". ".join(parts) + "."
