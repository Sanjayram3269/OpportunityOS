"""Enrichment layer — adds structured intelligence to normalized opportunities.

Deterministic enrichment only — no AI, no network calls, no fabrication.

Capabilities:
  - Skill extraction from opportunity descriptions/titles
  - Enhanced type classification with title-based inference
  - Location enrichment via the location intelligence module
  - Source metadata attachment
  - Category inference from metadata/tags
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.discovery.location import LocationInfo, analyze_location
from app.discovery.normalizer import NormalizedOpportunity
from app.matching.normalizer import extract_skills_from_text, normalize_skill


# ── Enhanced type classification ────────────────────────────────────────────

_TITLE_TYPE_PATTERNS: list[tuple[str, str]] = [
    # Internship patterns (check first — specific)
    (r"\bintern\b", "INTERNSHIP"),
    (r"\binternship\b", "INTERNSHIP"),
    (r"\bco-op\b", "INTERNSHIP"),
    (r"\bapprentice\b", "INTERNSHIP"),
    # Part-time patterns
    (r"\bpart[\s-]?time\b", "PART_TIME"),
    # Contract patterns (before engineer/developer to catch "Contract Engineer")
    (r"\bcontract\b", "CONTRACT"),
    (r"\bcontractor\b", "CONTRACT"),
    # Freelance patterns
    (r"\bfreelance\b", "FREELANCE"),
    (r"\bfreelancing\b", "FREELANCE"),
    # Research patterns (before generic engineer/developer)
    (r"\bresearch\b", "RESEARCH"),
    (r"\bresearcher\b", "RESEARCH"),
    (r"\bscientist\b", "RESEARCH"),
    (r"\bpostdoc\b", "RESEARCH"),
    (r"\bphd\b", "RESEARCH"),
    (r"\bthesis\b", "RESEARCH"),
    # Hackathon
    (r"\bhackathon\b", "HACKATHON"),
    (r"\bhack\b", "HACKATHON"),
    # Startup
    (r"\bstartup\b", "STARTUP"),
    (r"\bfounder\b", "STARTUP"),
    # Full-time patterns (broad — check after specific types)
    (r"\bfull[\s-]?time\b", "FULL_TIME"),
    (r"\bsenior\b", "FULL_TIME"),
    (r"\bstaff\b", "FULL_TIME"),
    (r"\blead\b", "FULL_TIME"),
    (r"\bprincipal\b", "FULL_TIME"),
    (r"\bdirector\b", "FULL_TIME"),
    (r"\bmanager\b", "FULL_TIME"),
    (r"\bengineer\b", "FULL_TIME"),
    (r"\bdeveloper\b", "FULL_TIME"),
    (r"\bsde\b", "FULL_TIME"),
    (r"\bswe\b", "FULL_TIME"),
]


def classify_opportunity_type(
    raw_type: str | None,
    title: str | None = None,
    description: str | None = None,
) -> str:
    """Enhanced opportunity type classification.

    Uses:
      1. Source-provided type if valid
      2. Title-based pattern matching
      3. Description-based pattern matching as fallback
      4. Falls back to OTHER if nothing matches

    Returns a canonical type string.
    """
    # 1. If source provides a known type, use it
    if raw_type and raw_type.upper() in {
        "INTERNSHIP", "FULL_TIME", "PART_TIME", "CONTRACT",
        "FREELANCE", "RESEARCH", "HACKATHON", "STARTUP",
        "REFERRAL", "VOLUNTEER", "OTHER",
    }:
        return raw_type.upper()

    # 2. Title-based inference
    if title:
        title_lower = title.lower()
        for pattern, opp_type in _TITLE_TYPE_PATTERNS:
            if re.search(pattern, title_lower):
                return opp_type

    # 3. Description-based inference (weaker signal)
    if description:
        desc_lower = description[:500].lower()  # limit to first 500 chars
        for pattern, opp_type in _TITLE_TYPE_PATTERNS:
            if re.search(pattern, desc_lower):
                return opp_type

    # 4. If source provided a type string (even unknown), keep it
    if raw_type:
        return raw_type.upper()

    return "OTHER"


# ── Skill extraction from opportunity ───────────────────────────────────────


def extract_opportunity_skills(
    title: str | None,
    description: str | None,
    metadata: dict | None = None,
) -> set[str]:
    """Extract normalized skill mentions from opportunity fields.

    Returns a set of canonical skill names (e.g. 'python', 'machine learning').
    """
    skills: set[str] = set()

    # Skills from title
    if title:
        skills |= extract_skills_from_text(title)

    # Skills from description
    if description:
        skills |= extract_skills_from_text(description)

    # Skills from metadata tags/categories
    if metadata:
        for key in ("tags", "skills", "categories"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                for tag in value.split(","):
                    tag = tag.strip()
                    if tag:
                        skills.add(normalize_skill(tag))

    return skills


# ── Category inference ──────────────────────────────────────────────────────

_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    (r"\bsoftware\b", "Software Engineering"),
    (r"\bweb\b", "Web Development"),
    (r"\bfrontend\b", "Frontend"),
    (r"\bfront[\s-]?end\b", "Frontend"),
    (r"\bbackend\b", "Backend"),
    (r"\bback[\s-]?end\b", "Backend"),
    (r"\bfull[\s-]?stack\b", "Full Stack"),
    (r"\bdata\b", "Data"),
    (r"\bmachine\s*learning\b", "Machine Learning"),
    (r"\bartificial\s*intelligence\b", "AI"),
    (r"\bai\b", "AI"),
    (r"\bml\b", "Machine Learning"),
    (r"\bdevops\b", "DevOps"),
    (r"\bcloud\b", "Cloud"),
    (r"\bsecurity\b", "Security"),
    (r"\bmobile\b", "Mobile"),
    (r"\bios\b", "Mobile"),
    (r"\bandroid\b", "Mobile"),
    (r"\bproduct\b", "Product"),
    (r"\bdesign\b", "Design"),
    (r"\bmarketing\b", "Marketing"),
    (r"\bsales\b", "Sales"),
    (r"\bresearch\b", "Research"),
    (r"\bfinance\b", "Finance"),
]


def infer_category(
    title: str | None,
    description: str | None,
    metadata: dict | None = None,
) -> str | None:
    """Infer a single category label from opportunity fields.

    Returns the first matching category, or None.
    """
    text_parts = []
    if title:
        text_parts.append(title)
    if description:
        text_parts.append(description[:300])
    if metadata:
        cat = metadata.get("category")
        if isinstance(cat, str) and cat:
            return cat  # Use source-provided category directly

    combined = " ".join(text_parts).lower()

    for pattern, category in _CATEGORY_KEYWORDS:
        if re.search(pattern, combined):
            return category

    return None


# ── Enrichment result ───────────────────────────────────────────────────────


@dataclass
class EnrichedOpportunity:
    """A normalized opportunity enriched with structured intelligence."""

    # Original normalized opportunity
    source_name: str
    external_id: str | None
    canonical_source_url: str | None
    normalized_title: str
    normalized_company_name: str
    description: str | None
    opportunity_type: str
    normalized_location: str | None
    deadline: object  # datetime | None
    salary_or_value: object  # Decimal | None
    metadata: dict

    # Enrichment fields
    location_info: LocationInfo | None = None
    extracted_skills: set[str] = field(default_factory=set)
    category: str | None = None
    is_remote: bool = False
    is_worldwide: bool = False
    country: str | None = None
    city: str | None = None


# ── Enrichment pipeline ────────────────────────────────────────────────────


def enrich(item: NormalizedOpportunity) -> EnrichedOpportunity:
    """Enrich a single NormalizedOpportunity with structured intelligence.

    Deterministic — no network calls, no AI, no fabrication.
    """
    # Location analysis
    location_info = analyze_location(item.normalized_location)

    # Enhanced type classification
    enriched_type = classify_opportunity_type(
        item.opportunity_type,
        title=item.normalized_title,
        description=item.description,
    )

    # Skill extraction
    skills = extract_opportunity_skills(
        item.normalized_title,
        item.description,
        item.metadata,
    )

    # Category inference
    category = infer_category(
        item.normalized_title,
        item.description,
        item.metadata,
    )

    return EnrichedOpportunity(
        source_name=item.source_name,
        external_id=item.external_id,
        canonical_source_url=item.canonical_source_url,
        normalized_title=item.normalized_title,
        normalized_company_name=item.normalized_company_name,
        description=item.description,
        opportunity_type=enriched_type,
        normalized_location=item.normalized_location,
        deadline=item.deadline,
        salary_or_value=item.salary_or_value,
        metadata=item.metadata,
        location_info=location_info,
        extracted_skills=skills,
        category=category,
        is_remote=location_info.is_remote,
        is_worldwide=location_info.is_worldwide,
        country=location_info.country,
        city=location_info.city,
    )


def enrich_all(items: list[NormalizedOpportunity]) -> list[EnrichedOpportunity]:
    """Enrich a batch of normalized opportunities."""
    return [enrich(item) for item in items]
