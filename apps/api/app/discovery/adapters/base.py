from __future__ import annotations

from abc import ABC, abstractmethod

from app.discovery.models import RawOpportunity


class SourceAdapter(ABC):
    """Base class for discovery source adapters.

    Every concrete adapter must implement:
      - ``source_name``: a stable, unique string identifier for the source
      - ``discover()``: returns a list of ``RawOpportunity`` records

    To add a new source:
      1. Create a new module in ``app/discovery/adapters/``
      2. Subclass ``SourceAdapter``
      3. Implement ``source_name`` and ``discover()``
      4. Register the adapter in the discovery service's adapter registry

    Example::

        class MyAdapter(SourceAdapter):
            source_name = "my_source"

            def discover(self) -> list[RawOpportunity]:
                # fetch from your source
                return [...]
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Canonical, unique identifier for this source (e.g. 'hackernews')."""
        ...

    @abstractmethod
    def discover(self) -> list[RawOpportunity]:
        """Fetch and return raw opportunity records from this source.

        The adapter is responsible for making any external calls (HTTP, etc.)
        and converting the response into ``RawOpportunity`` instances.

        Returns:
            A list of raw opportunity records.  May be empty if nothing was
            found.
        """
        ...
