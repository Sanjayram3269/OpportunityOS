"""Arbeitnow source adapter — fetches jobs from the public Arbeitnow API.

API docs: https://www.arbeitnow.com/blog/job-board-api
Endpoint: https://www.arbeitnow.com/api/job-board-api

No authentication required.  Rate limits are generous and undocumented;
the adapter fetches once per invocation.

Data is primarily European job postings sourced from Applicant Tracking
Systems (Greenhouse, SmartRecruiters, Join.com, Team Tailor, etc.).
Includes remote-flagged roles and jobs with visa sponsorship.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.discovery.adapters.base import SourceAdapter
from app.discovery.models import RawOpportunity

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
REQUEST_TIMEOUT = 30  # seconds

# Arbeitnow job_type strings → our canonical opportunity type
_JOB_TYPE_MAP: dict[str, str] = {
    "full_time": "FULL_TIME",
    "part_time": "PART_TIME",
    "contract": "CONTRACT",
    "freelance": "FREELANCE",
    "internship": "INTERNSHIP",
    "temporary": "CONTRACT",
    "volunteer": "VOLUNTEER",
}

# ── Adapter ───────────────────────────────────────────────────────────────


class ArbeitnowAdapter(SourceAdapter):
    """Discovers job opportunities from the public Arbeitnow API.

    Usage::

        adapter = ArbeitnowAdapter()
        raw_opps = adapter.discover()

    Configuration (optional, via Settings):
        - ``arbeitnow_api_url``: Override the API endpoint
        - ``arbeitnow_request_timeout``: Override request timeout in seconds
    """

    source_name: str = "arbeitnow"

    def __init__(
        self,
        *,
        api_url: str | None = None,
        request_timeout: int | None = None,
    ) -> None:
        self._api_url = api_url or ARBEITNOW_API_URL
        self._timeout = request_timeout or REQUEST_TIMEOUT

    # ── Public API ────────────────────────────────────────────────────

    def discover(self) -> list[RawOpportunity]:
        """Fetch all active jobs from Arbeitnow.

        Returns a list of ``RawOpportunity`` records.
        Raises on network errors, timeouts, or malformed responses —
        the caller (``run_source``) is responsible for catching errors.
        """
        data = self._fetch_jobs()

        raw_opportunities: list[RawOpportunity] = []
        for job in data:
            parsed = self._parse_job(job)
            if parsed is not None:
                raw_opportunities.append(parsed)

        logger.info(
            "Arbeitnow adapter: fetched %d jobs, parsed %d",
            len(data),
            len(raw_opportunities),
        )
        return raw_opportunities

    # ── Internal helpers ──────────────────────────────────────────────

    def _fetch_jobs(self) -> list[dict[str, Any]]:
        """Make the HTTP request and return the raw jobs list.

        Raises on network errors, timeouts, or malformed responses.
        """
        response = httpx.get(
            self._api_url,
            timeout=self._timeout,
            headers={"User-Agent": "OpportunityOS/0.1 (discovery-engine)"},
        )
        response.raise_for_status()

        body = response.json()

        if not isinstance(body, dict):
            raise ValueError(f"Expected JSON object, got {type(body).__name__}")

        data = body.get("data")
        if not isinstance(data, list):
            raise ValueError(f"Expected 'data' list, got {type(data).__name__}")

        return data

    def _parse_job(self, job: dict[str, Any]) -> RawOpportunity | None:
        """Convert a single Arbeitnow job record into a ``RawOpportunity``.

        Returns ``None`` if the record is missing required fields.
        """
        title = self._extract_str(job.get("title"))
        company_name = self._extract_str(job.get("company_name"))

        if not title or not company_name:
            logger.debug(
                "Skipping Arbeitnow job with missing title or company: %s",
                job.get("slug"),
            )
            return None

        # External ID — use slug (stable, unique per posting)
        external_id = self._extract_str(job.get("slug"))

        # URL — direct link to the job posting
        source_url = self._extract_str(job.get("url")) or None

        # Description — may contain HTML, keep as-is
        description = self._extract_str(job.get("description")) or None

        # Opportunity type — map from job_types array
        raw_job_types = job.get("job_types") or []
        if isinstance(raw_job_types, list) and raw_job_types:
            # Use first recognized type
            opportunity_type = self._map_job_types(raw_job_types)
        else:
            # No job_types — infer from title
            opportunity_type = self._infer_type_from_title(title)

        # Location
        location = self._extract_str(job.get("location")) or None

        # Remote flag — append to location if remote
        remote = job.get("remote")
        if remote is True and location:
            location = f"{location} (Remote)"
        elif remote is True:
            location = "Remote"

        # Tags — store in metadata
        tags = job.get("tags") or []

        # created_at — Unix timestamp, store in metadata as publication date
        created_at_raw = job.get("created_at")

        metadata: dict[str, str | int | float | bool | None] = {}
        if isinstance(tags, list) and tags:
            metadata["tags"] = ", ".join(str(t) for t in tags)
        if isinstance(created_at_raw, (int, float)):
            metadata["created_at"] = int(created_at_raw)

        return RawOpportunity(
            source_name=self.source_name,
            external_id=external_id,
            source_url=source_url,
            title=title,
            company_name=company_name,
            description=description,
            opportunity_type=opportunity_type,
            location=location,
            deadline=None,  # Arbeitnow does not provide deadlines
            salary_or_value=None,  # Arbeitnow does not provide salary data
            metadata=metadata,
        )

    # ── Type mapping ──────────────────────────────────────────────────

    def _map_job_types(self, job_types: list[str]) -> str:
        """Map Arbeitnow job_types to our canonical type."""
        for jt in job_types:
            mapped = _JOB_TYPE_MAP.get(str(jt).lower())
            if mapped is not None:
                return mapped
        return "OTHER"

    # ── Type inference from title ─────────────────────────────────────

    _TITLE_TYPE_KEYWORDS: list[tuple[str, str]] = [
        ("intern", "INTERNSHIP"),
        ("full-time", "FULL_TIME"),
        ("full time", "FULL_TIME"),
        ("full-stack", "FULL_TIME"),
        ("full stack", "FULL_TIME"),
        ("part-time", "PART_TIME"),
        ("part time", "PART_TIME"),
        ("contract", "CONTRACT"),
        ("freelance", "FREELANCE"),
        ("startup", "STARTUP"),
        ("research", "RESEARCH"),
        ("hackathon", "HACKATHON"),
    ]

    def _infer_type_from_title(self, title: str) -> str:
        """Best-effort type inference from job title when job_types is empty."""
        title_lower = title.lower()
        for keyword, opp_type in self._TITLE_TYPE_KEYWORDS:
            if keyword in title_lower:
                return opp_type
        return "OTHER"

    # ── Field extraction helpers ──────────────────────────────────────

    @staticmethod
    def _extract_str(value: Any) -> str | None:
        """Extract a non-empty stripped string, or None."""
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None
