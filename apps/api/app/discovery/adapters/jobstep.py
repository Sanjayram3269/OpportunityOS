"""JobStep stub adapter — documents the integration boundary.

No API calls are made.  This adapter exists to:
  - Document that JobStep is a planned source
  - Report "requires_authorized_integration" when queried
  - Ensure the automation engine can skip it gracefully

DO NOT scrape or bypass authentication.
A legitimate JobStep integration requires an authorized partnership.
"""

from __future__ import annotations

import logging

from app.discovery.adapters.base import SourceAdapter
from app.discovery.models import RawOpportunity

logger = logging.getLogger(__name__)


class JobStepAdapter(SourceAdapter):
    """Stub — requires authorized JobStep integration."""

    source_name: str = "jobstep"

    def discover(self) -> list[RawOpportunity]:
        raise NotImplementedError(
            "JobStep integration requires authorized partnership. "
            "This adapter is a stub for future integration."
        )
