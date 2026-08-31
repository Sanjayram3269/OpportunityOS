"""Remotive source adapter — fetches remote jobs from the public Remotive API.

API docs: https://github.com/remotive-com/remote-jobs-api
Endpoint: https://remotive.com/api/remote-jobs

Rate limits (per Remotive ToS):
  - Max 2 requests per minute
  - Recommended max 4 requests per day

This adapter is read-only and fetches from a public, documented endpoint.
No authentication is required.
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

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"
REQUEST_TIMEOUT = 30  # seconds

# Remotive job_type → our canonical opportunity type
_JOB_TYPE_MAP: dict[str, str] = {
    "full_time": "FULL_TIME",
    "part_time": "PART_TIME",
    "contract": "CONTRACT",
    "freelance": "FREELANCE",
    "internship": "INTERNSHIP",
}


# ── Adapter ───────────────────────────────────────────────────────────────


class RemotiveAdapter(SourceAdapter):
    """Discovers remote job opportunities from the public Remotive API.

    Usage::

        adapter = RemotiveAdapter()
        raw_opps = adapter.discover()

    Configuration (optional, via Settings):
        - ``remotive_api_url``: Override the API endpoint
        - ``remotive_request_timeout``: Override request timeout in seconds
    """

    source_name: str = "remotive"

    def __init__(
        self,
        *,
        api_url: str | None = None,
        request_timeout: int | None = None,
    ) -> None:
        self._api_url = api_url or REMOTIVE_API_URL
        self._timeout = request_timeout or REQUEST_TIMEOUT

    # ── Public API ────────────────────────────────────────────────────

    def discover(self) -> list[RawOpportunity]:
        """Fetch all active remote jobs from Remotive.

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
            "Remotive adapter: fetched %d jobs, parsed %d",
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

        jobs = body.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError(f"Expected 'jobs' list, got {type(jobs).__name__}")

        return jobs

    def _parse_job(self, job: dict[str, Any]) -> RawOpportunity | None:
        """Convert a single Remotive job record into a ``RawOpportunity``.

        Returns ``None`` if the record is missing required fields.
        """
        title = self._extract_str(job.get("title"))
        company_name = self._extract_str(job.get("company_name"))

        if not title or not company_name:
            logger.debug(
                "Skipping Remotive job with missing title or company: %s",
                job.get("id"),
            )
            return None

        # External ID — Remotive integer ID, stored as string
        external_id = self._to_str_or_none(job.get("id"))

        # URL — prefer the Remotive listing URL
        source_url = self._extract_str(job.get("url")) or None

        # Description — may contain HTML, keep as-is
        description = self._extract_str(job.get("description")) or None

        # Opportunity type — map from Remotive's job_type field
        raw_job_type = self._extract_str(job.get("job_type"))
        opportunity_type = _JOB_TYPE_MAP.get(
            raw_job_type.lower() if raw_job_type else "",
            "OTHER",
        )

        # If job_type is missing, try to infer from title
        if raw_job_type is None:
            opportunity_type = self._infer_type_from_title(title)

        # Location — "candidate_required_location" field
        location = self._extract_str(job.get("candidate_required_location")) or None

        # Salary — freeform text, store as-is in metadata
        salary_raw = self._extract_str(job.get("salary")) or None

        # Publication date
        publication_date = self._parse_datetime(job.get("publication_date"))

        # Category — store in metadata
        category = self._extract_str(job.get("category")) or None

        metadata: dict[str, str | int | float | bool | None] = {}
        if category:
            metadata["category"] = category
        if salary_raw:
            metadata["salary_text"] = salary_raw

        return RawOpportunity(
            source_name=self.source_name,
            external_id=external_id,
            source_url=source_url,
            title=title,
            company_name=company_name,
            description=description,
            opportunity_type=opportunity_type,
            location=location,
            deadline=publication_date,
            salary_or_value=None,  # salary is freeform text on Remotive
            metadata=metadata,
        )

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
        """Best-effort type inference from job title when job_type is absent."""
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

    @staticmethod
    def _to_str_or_none(value: Any) -> str | None:
        """Convert a value to string if not None."""
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse an ISO-8601 datetime string, returning None on failure."""
        if value is None:
            return None
        try:
            s = str(value).strip()
            if not s:
                return None
            # Handle both timezone-aware and naive ISO strings
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            logger.debug("Failed to parse datetime: %s", value)
            return None
