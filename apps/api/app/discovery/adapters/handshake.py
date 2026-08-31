"""Handshake stub adapter — documents the integration boundary.

No API calls are made.  This adapter exists to:
  - Document that Handshake is a planned source
  - Report "requires_authorized_integration" when queried
  - Ensure the automation engine can skip it gracefully

DO NOT scrape or bypass authentication.
Handshake is a university career platform that requires institutional API access.
"""

from __future__ import annotations

import logging

from app.discovery.adapters.base import SourceAdapter
from app.discovery.models import RawOpportunity

logger = logging.getLogger(__name__)


class HandshakeAdapter(SourceAdapter):
    """Stub — requires authorized Handshake API integration."""

    source_name: str = "handshake"

    def discover(self) -> list[RawOpportunity]:
        raise NotImplementedError(
            "Handshake integration requires institutional API access. "
            "This adapter is a stub for future integration."
        )
