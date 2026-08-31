"""Adapter registry — maps source names to adapter classes.

To register a new adapter:
  1. Create a new module in ``app/discovery/adapters/``
  2. Subclass ``SourceAdapter``
  3. Add an entry to the ``ADAPTERS`` dict below

The registry is a plain dict for simplicity.  Adapters are instantiated
lazily (per call) so no global state is held.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.discovery.adapters.base import SourceAdapter


# ── Active adapters (public, no auth required) ─────────────────────────────

def _lazy_remotive() -> type["SourceAdapter"]:
    from app.discovery.adapters.remotive import RemotiveAdapter
    return RemotiveAdapter

def _lazy_arbeitnow() -> type["SourceAdapter"]:
    from app.discovery.adapters.arbeitnow import ArbeitnowAdapter
    return ArbeitnowAdapter

def _lazy_himalayas() -> type["SourceAdapter"]:
    from app.discovery.adapters.himalayas import HimalayasAdapter
    return HimalayasAdapter


# ── Stub adapters (require authorized integration) ──────────────────────────

def _lazy_linkedin() -> type["SourceAdapter"]:
    from app.discovery.adapters.linkedin import LinkedInAdapter
    return LinkedInAdapter

def _lazy_handshake() -> type["SourceAdapter"]:
    from app.discovery.adapters.handshake import HandshakeAdapter
    return HandshakeAdapter

def _lazy_jobstep() -> type["SourceAdapter"]:
    from app.discovery.adapters.jobstep import JobStepAdapter
    return JobStepAdapter


# source_name → factory that returns the adapter class (lazy import)
_ADAPTER_FACTORIES: dict[str, callable] = {
    "arbeitnow": _lazy_arbeitnow,
    "himalayas": _lazy_himalayas,
    "remotive": _lazy_remotive,
    "linkedin": _lazy_linkedin,
    "handshake": _lazy_handshake,
    "jobstep": _lazy_jobstep,
}

# Sources that require authorized integration (will raise NotImplementedError)
_AUTH_REQUIRED_SOURCES: set[str] = {"linkedin", "handshake", "jobstep"}


def get_adapter_class(source_name: str) -> type["SourceAdapter"] | None:
    """Return the adapter class for the given source name, or None."""
    factory = _ADAPTER_FACTORIES.get(source_name.lower())
    if factory is None:
        return None
    return factory()


def list_source_names() -> list[str]:
    """Return all registered source names."""
    return sorted(_ADAPTER_FACTORIES.keys())


def list_active_source_names() -> list[str]:
    """Return source names that are actively fetchable (no auth required)."""
    return sorted(
        name for name in _ADAPTER_FACTORIES
        if name not in _AUTH_REQUIRED_SOURCES
    )


def is_auth_required(source_name: str) -> bool:
    """Check if a source requires authorized integration."""
    return source_name.lower() in _AUTH_REQUIRED_SOURCES


def create_adapter(
    source_name: str,
    **kwargs: object,
) -> "SourceAdapter":
    """Instantiate an adapter by source name.

    Raises ``ValueError`` if the source name is not registered.
    """
    cls = get_adapter_class(source_name)
    if cls is None:
        available = ", ".join(list_source_names())
        raise ValueError(
            f"Unknown source: {source_name!r}. "
            f"Available sources: {available}"
        )
    return cls(**kwargs)
