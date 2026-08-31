"""Source metadata — describes each discovery source's capabilities and requirements.

This module provides a structured description of each source adapter without
exposing secrets or implementation details.  The metadata is used by:
  - The discovery API (GET /discovery/sources with rich info)
  - The automation engine (which sources to attempt)
  - The frontend (display source capabilities and health)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceMetadata:
    """Immutable metadata describing a discovery source."""

    name: str
    display_name: str
    source_type: str  # "job_board", "career_portal", "social", "rss", "api"
    description: str = ""
    requires_auth: bool = False
    enabled: bool = True
    geographic_coverage: list[str] = field(default_factory=lambda: ["GLOBAL"])
    supported_types: list[str] = field(default_factory=list)
    supports_remote: bool = True
    supports_deadline: bool = False
    supports_salary: bool = False
    rate_limit_note: str = ""
    source_url: str = ""
    adapter_available: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "source_type": self.source_type,
            "description": self.description,
            "requires_auth": self.requires_auth,
            "enabled": self.enabled,
            "geographic_coverage": self.geographic_coverage,
            "supported_types": self.supported_types,
            "supports_remote": self.supports_remote,
            "supports_deadline": self.supports_deadline,
            "supports_salary": self.supports_salary,
            "rate_limit_note": self.rate_limit_note,
            "source_url": self.source_url,
            "adapter_available": self.adapter_available,
        }


# ── Known source metadata ──────────────────────────────────────────────────

REMOTIVE_METADATA = SourceMetadata(
    name="remotive",
    display_name="Remotive",
    source_type="job_board",
    description="Remote-only job board with curated listings across multiple categories.",
    requires_auth=False,
    enabled=True,
    geographic_coverage=["GLOBAL"],
    supported_types=["FULL_TIME", "PART_TIME", "CONTRACT", "FREELANCE", "INTERNSHIP", "OTHER"],
    supports_remote=True,
    supports_deadline=False,  # publication_date, not application deadline
    supports_salary=False,  # salary is freeform text in metadata
    rate_limit_note="Max 2 requests/minute, recommended max 4/day",
    source_url="https://remotive.com",
    adapter_available=True,
)

ARBEITNOW_METADATA = SourceMetadata(
    name="arbeitnow",
    display_name="Arbeitnow",
    source_type="job_board",
    description="European/international job board aggregating ATS listings. Includes remote roles.",
    requires_auth=False,
    enabled=True,
    geographic_coverage=["EUROPE", "GLOBAL"],
    supported_types=["FULL_TIME", "PART_TIME", "CONTRACT", "FREELANCE", "INTERNSHIP", "OTHER"],
    supports_remote=True,
    supports_deadline=False,
    supports_salary=False,
    rate_limit_note="Generous, undocumented rate limits",
    source_url="https://www.arbeitnow.com",
    adapter_available=True,
)

HIMALAYAS_METADATA = SourceMetadata(
    name="himalayas",
    display_name="Himalayas",
    source_type="job_board",
    description="Remote jobs board with salary transparency and company profiles. Strong remote-first listings.",
    requires_auth=False,
    enabled=True,
    geographic_coverage=["GLOBAL"],
    supported_types=["FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP", "OTHER"],
    supports_remote=True,
    supports_deadline=False,
    supports_salary=False,  # salary data may exist but is not reliably structured
    rate_limit_note="Public API, reasonable usage expected",
    source_url="https://himalayas.app",
    adapter_available=True,
)

LINKEDIN_METADATA = SourceMetadata(
    name="linkedin",
    display_name="LinkedIn",
    source_type="social",
    description="Professional network with comprehensive job listings. Requires authorized API integration.",
    requires_auth=True,
    enabled=False,
    geographic_coverage=["GLOBAL"],
    supported_types=["FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP", "FREELANCE", "RESEARCH", "OTHER"],
    supports_remote=True,
    supports_deadline=False,
    supports_salary=False,
    rate_limit_note="Requires authorized API access",
    source_url="https://www.linkedin.com",
    adapter_available=False,
)

HANDSHAKE_METADATA = SourceMetadata(
    name="handshake",
    display_name="Handshake",
    source_type="career_portal",
    description="University career platform for student/internship opportunities. Requires institutional API access.",
    requires_auth=True,
    enabled=False,
    geographic_coverage=["US", "GLOBAL"],
    supported_types=["INTERNSHIP", "FULL_TIME", "PART_TIME", "OTHER"],
    supports_remote=True,
    supports_deadline=False,
    supports_salary=False,
    rate_limit_note="Requires institutional API access",
    source_url="https://joinhandshake.com",
    adapter_available=False,
)

JOBSTEP_METADATA = SourceMetadata(
    name="jobstep",
    display_name="JobStep",
    source_type="job_board",
    description="AI-powered job matching platform. Requires authorized integration.",
    requires_auth=True,
    enabled=False,
    geographic_coverage=["GLOBAL"],
    supported_types=["FULL_TIME", "INTERNSHIP", "CONTRACT", "OTHER"],
    supports_remote=True,
    supports_deadline=False,
    supports_salary=False,
    rate_limit_note="Requires authorized integration",
    source_url="https://www.jobstep.ai",
    adapter_available=False,
)

# ── Registry ────────────────────────────────────────────────────────────────

_METADATA_REGISTRY: dict[str, SourceMetadata] = {
    "remotive": REMOTIVE_METADATA,
    "arbeitnow": ARBEITNOW_METADATA,
    "himalayas": HIMALAYAS_METADATA,
    "linkedin": LINKEDIN_METADATA,
    "handshake": HANDSHAKE_METADATA,
    "jobstep": JOBSTEP_METADATA,
}


def get_source_metadata(source_name: str) -> SourceMetadata | None:
    """Return metadata for a registered source, or None."""
    return _METADATA_REGISTRY.get(source_name.lower())


def list_source_metadata() -> list[SourceMetadata]:
    """Return metadata for all registered sources."""
    return list(_METADATA_REGISTRY.values())


def list_enabled_sources() -> list[SourceMetadata]:
    """Return metadata for all enabled sources with available adapters."""
    return [m for m in _METADATA_REGISTRY.values() if m.enabled and m.adapter_available]
