"""Himalayas source adapter — fetches remote jobs from the public Himalayas API.

API docs: https://himalayas.app/docs/remote-jobs-api
Browse endpoint: https://himalayas.app/jobs/api
Search endpoint: https://himalayas.app/jobs/api/search

No authentication required.  Data is refreshed every 24 hours.
Rate limited — do not poll more than once per day.

This adapter uses the search endpoint filtered by country to focus on
India-based and India-eligible remote opportunities.  It also fetches
worldwide roles that are open to India candidates.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.discovery.adapters.base import SourceAdapter
from app.discovery.models import RawOpportunity

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

HIMALAYAS_SEARCH_URL = "https://himalayas.app/jobs/api/search"
REQUEST_TIMEOUT = 30  # seconds
DEFAULT_LIMIT = 20  # max per request

# Himalayas employmentType → our canonical opportunity type
_EMPLOYMENT_TYPE_MAP: dict[str, str] = {
    "full time": "FULL_TIME",
    "part time": "PART_TIME",
    "contract": "CONTRACT",
    "intern": "INTERNSHIP",
    "freelance": "FREELANCE",
}


# ── Adapter ───────────────────────────────────────────────────────────────


class HimalayasAdapter(SourceAdapter):
    """Discovers India-focused remote job opportunities from Himalayas.

    Uses the search endpoint filtered by country=India to find roles
    that are based in or open to candidates in India.

    Usage::

        adapter = HimalayasAdapter()
        raw_opps = adapter.discover()

    Configuration (optional, via Settings):
        - ``himalayas_search_url``: Override the search API endpoint
        - ``himalayas_request_timeout``: Override request timeout in seconds
    """

    source_name: str = "himalayas"

    def __init__(
        self,
        *,
        search_url: str | None = None,
        request_timeout: int | None = None,
    ) -> None:
        self._search_url = search_url or HIMALAYAS_SEARCH_URL
        self._timeout = request_timeout or REQUEST_TIMEOUT

    # ── Public API ────────────────────────────────────────────────────

    def discover(self) -> list[RawOpportunity]:
        """Fetch India-eligible remote jobs from Himalayas.

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
            "Himalayas adapter: fetched %d jobs, parsed %d",
            len(data),
            len(raw_opportunities),
        )
        return raw_opportunities

    # ── Internal helpers ──────────────────────────────────────────────

    def _fetch_jobs(self) -> list[dict[str, Any]]:
        """Make the HTTP request to the search endpoint and return jobs.

        Filters for India-based and India-eligible remote roles.
        Raises on network errors, timeouts, or malformed responses.
        """
        params = {
            "country": "India",
            "limit": DEFAULT_LIMIT,
        }

        response = httpx.get(
            self._search_url,
            params=params,
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
        """Convert a single Himalayas job record into a ``RawOpportunity``.

        Returns ``None`` if the record is missing required fields.
        """
        title = self._extract_str(job.get("title"))
        company_name = self._extract_str(job.get("companyName"))

        if not title or not company_name:
            logger.debug(
                "Skipping Himalayas job with missing title or company: %s",
                job.get("guid"),
            )
            return None

        # External ID — guid (stable URL-based identifier)
        external_id = self._extract_str(job.get("guid"))

        # Source URL — applicationLink
        source_url = self._extract_str(job.get("applicationLink")) or None

        # Description — HTML, keep as-is
        description = self._extract_str(job.get("description")) or None

        # Opportunity type — map from employmentType
        raw_employment = self._extract_str(job.get("employmentType"))
        opportunity_type = _EMPLOYMENT_TYPE_MAP.get(
            raw_employment.lower() if raw_employment else "",
            "OTHER",
        )

        # If employment type is missing, try to infer from title
        if raw_employment is None:
            opportunity_type = self._infer_type_from_title(title)

        # Location — from locationRestrictions
        location_restrictions = job.get("locationRestrictions") or []
        if isinstance(location_restrictions, list) and location_restrictions:
            # Use first country restriction; if "India" is present, show it
            location = str(location_restrictions[0])
        else:
            location = "Worldwide"

        # Salary — parse min/max into a single representative value
        salary_or_value = self._parse_salary(job)

        # Deadline — expiryDate (Unix timestamp), actual application deadline
        deadline = self._parse_timestamp(job.get("expiryDate"))

        # Publication date — for metadata only
        pub_date = self._parse_timestamp(job.get("pubDate"))

        # Categories and seniority — store in metadata
        categories = job.get("categories") or []
        seniority = job.get("seniority") or []
        currency = self._extract_str(job.get("currency"))

        metadata: dict[str, str | int | float | bool | None] = {}
        if isinstance(categories, list) and categories:
            metadata["categories"] = ", ".join(str(c) for c in categories[:10])
        if isinstance(seniority, list) and seniority:
            metadata["seniority"] = ", ".join(str(s) for s in seniority)
        if currency:
            metadata["currency"] = currency
        if pub_date is not None:
            metadata["pub_date"] = int(pub_date.timestamp())

        return RawOpportunity(
            source_name=self.source_name,
            external_id=external_id,
            source_url=source_url,
            title=title,
            company_name=company_name,
            description=description,
            opportunity_type=opportunity_type,
            location=location,
            deadline=deadline,
            salary_or_value=salary_or_value,
            metadata=metadata,
        )

    # ── Salary parsing ────────────────────────────────────────────────

    def _parse_salary(self, job: dict[str, Any]) -> Decimal | None:
        """Parse minSalary from the job record into a Decimal.

        Returns the minimum salary as a numeric value, or None if
        not available.
        """
        min_salary = job.get("minSalary")
        if min_salary is None:
            return None
        try:
            return Decimal(str(min_salary))
        except (ValueError, TypeError):
            return None

    # ── Timestamp parsing ─────────────────────────────────────────────

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse a Unix timestamp (int/float) into a UTC datetime."""
        if value is None:
            return None
        try:
            ts = int(value)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            logger.debug("Failed to parse timestamp: %s", value)
            return None

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
        """Best-effort type inference from job title when employmentType is absent."""
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
