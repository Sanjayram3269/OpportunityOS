from __future__ import annotations

import re
import unicodedata

from app.discovery.models import RawOpportunity


# ── Canonical type mapping ────────────────────────────────────────────────

_TYPE_ALIASES: dict[str, str] = {
    "intern": "INTERNSHIP",
    "internship": "INTERNSHIP",
    "internships": "INTERNSHIP",
    "full-time": "FULL_TIME",
    "full time": "FULL_TIME",
    "fulltime": "FULL_TIME",
    "ft": "FULL_TIME",
    "part-time": "PART_TIME",
    "part time": "PART_TIME",
    "contract": "CONTRACT",
    "freelance": "FREELANCE",
    "freelancing": "FREELANCE",
    "startup": "STARTUP",
    "research": "RESEARCH",
    "hackathon": "HACKATHON",
    "hackathons": "HACKATHON",
    "referral": "REFERRAL",
    "referrals": "REFERRAL",
    "volunteer": "VOLUNTEER",
    "volunteering": "VOLUNTEER",
    "other": "OTHER",
}

# Well-known types pass through directly
_KNOWN_TYPES: set[str] = {
    "INTERNSHIP",
    "FULL_TIME",
    "PART_TIME",
    "CONTRACT",
    "FREELANCE",
    "STARTUP",
    "RESEARCH",
    "HACKATHON",
    "REFERRAL",
    "VOLUNTEER",
    "OTHER",
}


# ── String helpers ────────────────────────────────────────────────────────


def _collapse_whitespace(text: str) -> str:
    """Strip, normalize unicode, and collapse runs of whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_url(url: str | None) -> str | None:
    if url is None:
        return None
    url = url.strip()
    url = re.sub(r"#.*$", "", url)  # drop fragment
    url = re.sub(r"/+$", "", url)  # drop trailing slash
    if not url:
        return None
    return url.lower()


def _normalize_company_name(name: str) -> str:
    name = _collapse_whitespace(name)
    return name


def _normalize_title(title: str) -> str:
    title = _collapse_whitespace(title)
    return title


def _normalize_location(location: str | None) -> str | None:
    if location is None:
        return None
    location = _collapse_whitespace(location)
    if not location:
        return None
    return location


def normalize_type(raw_type: str | None) -> str:
    """Map a raw type string to a canonical uppercase type constant."""
    if raw_type is None:
        return "OTHER"
    raw_lower = raw_type.strip().lower()
    if raw_lower in _TYPE_ALIASES:
        return _TYPE_ALIASES[raw_lower]
    upper = raw_type.strip().upper()
    if upper in _KNOWN_TYPES:
        return upper
    return "OTHER"


# ── Normalized opportunity ────────────────────────────────────────────────


class NormalizedOpportunity:
    """A fully normalized opportunity record ready for deduplication and ingestion.

    This is a plain class (not a Pydantic model) to keep the normalization
    layer free of serialization concerns and to make equality / hashing
    straightforward for the deduplicator.
    """

    __slots__ = (
        "source_name",
        "external_id",
        "canonical_source_url",
        "normalized_title",
        "normalized_company_name",
        "description",
        "opportunity_type",
        "normalized_location",
        "deadline",
        "salary_or_value",
        "metadata",
    )

    def __init__(
        self,
        *,
        source_name: str,
        external_id: str | None,
        canonical_source_url: str | None,
        normalized_title: str,
        normalized_company_name: str,
        description: str | None,
        opportunity_type: str,
        normalized_location: str | None,
        deadline,
        salary_or_value,
        metadata: dict,
    ) -> None:
        self.source_name = source_name
        self.external_id = external_id
        self.canonical_source_url = canonical_source_url
        self.normalized_title = normalized_title
        self.normalized_company_name = normalized_company_name
        self.description = description
        self.opportunity_type = opportunity_type
        self.normalized_location = normalized_location
        self.deadline = deadline
        self.salary_or_value = salary_or_value
        self.metadata = metadata

    def __repr__(self) -> str:
        return (
            f"NormalizedOpportunity(source={self.source_name!r}, "
            f"company={self.normalized_company_name!r}, "
            f"title={self.normalized_title!r})"
        )


# ── Public API ────────────────────────────────────────────────────────────


def normalize(raw: RawOpportunity) -> NormalizedOpportunity:
    """Convert a single ``RawOpportunity`` into a ``NormalizedOpportunity``.

    This function is pure / deterministic — no database or network calls.
    """
    return NormalizedOpportunity(
        source_name=raw.source_name.strip().lower(),
        external_id=raw.external_id.strip() if raw.external_id else None,
        canonical_source_url=_normalize_url(raw.source_url),
        normalized_title=_normalize_title(raw.title),
        normalized_company_name=_normalize_company_name(raw.company_name),
        description=raw.description.strip() if raw.description else None,
        opportunity_type=normalize_type(raw.opportunity_type),
        normalized_location=_normalize_location(raw.location),
        deadline=raw.deadline,
        salary_or_value=raw.salary_or_value,
        metadata=raw.metadata,
    )


def normalize_all(raw_items: list[RawOpportunity]) -> list[NormalizedOpportunity]:
    """Normalize a batch of raw opportunities."""
    return [normalize(item) for item in raw_items]
