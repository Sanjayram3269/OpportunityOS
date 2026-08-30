from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RawOpportunity(BaseModel):
    """A raw opportunity record as returned by a source adapter.

    Fields are intentionally permissive — not every source provides every
    field.  The normalizer will fill in defaults and clean up values before
    the ingestion layer persists them.
    """

    source_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Canonical name of the source (e.g. 'linkedin', 'hackernews')",
    )
    external_id: str | None = Field(
        default=None,
        max_length=500,
        description="Source-specific identifier for deduplication",
    )
    source_url: str | None = Field(
        default=None,
        max_length=1000,
        description="Direct URL to the opportunity posting",
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=300,
    )
    company_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )
    description: str | None = None
    opportunity_type: str | None = Field(
        default=None,
        max_length=50,
        description="e.g. INTERNSHIP, FULL_TIME, FREELANCE, HACKATHON",
    )
    location: str | None = Field(
        default=None,
        max_length=200,
    )
    deadline: datetime | None = None
    salary_or_value: Decimal | None = None

    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Source-specific extra data that doesn't map to a known field",
    )


class IngestionResult(BaseModel):
    """Summary of what happened when a batch of raw opportunities was ingested."""

    source_name: str
    raw_count: int
    ingested: int
    duplicates_skipped: int
    companies_created: int
    errors: list[str] = Field(default_factory=list)
