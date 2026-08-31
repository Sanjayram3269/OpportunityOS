"""LinkedIn stub adapter — documents the integration boundary.

No API calls are made.  This adapter exists to:
  - Document that LinkedIn is a planned source
  - Report "requires_authorized_integration" when queried
  - Ensure the automation engine can skip it gracefully

DO NOT implement scraping, browser automation, or authentication bypass.
A legitimate LinkedIn integration requires an authorized API partner relationship.
"""

from __future__ import annotations

import logging

from app.discovery.adapters.base import SourceAdapter
from app.discovery.models import RawOpportunity

logger = logging.getLogger(__name__)


class LinkedInAdapter(SourceAdapter):
    """Stub — requires authorized LinkedIn API integration."""

    source_name: str = "linkedin"

    def discover(self) -> list[RawOpportunity]:
        raise NotImplementedError(
            "LinkedIn integration requires authorized API access. "
            "This adapter is a stub for future integration."
        )
