"""Location intelligence — normalizes and structures location information.

Provides deterministic location analysis without fabricating data.
Supports common patterns like Bengaluru/Bangalore, Remote, Worldwide, etc.

All fields are optional — missing data produces None, not guesses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LocationInfo:
    """Structured location information derived from a raw location string."""

    raw: str | None
    normalized: str | None
    city: str | None
    country: str | None
    is_remote: bool
    is_worldwide: bool
    is_hybrid: bool
    is_onsite: bool


# ── Canonical city aliases ──────────────────────────────────────────────────

_CITY_ALIASES: dict[str, tuple[str, str]] = {
    # city → (canonical_city, country)
    "bengaluru": ("Bengaluru", "India"),
    "bangalore": ("Bengaluru", "India"),
    "bangaluru": ("Bengaluru", "India"),
    "bangalore, india": ("Bengaluru", "India"),
    "bengaluru, india": ("Bengaluru", "India"),
    "bangalore india": ("Bengaluru", "India"),
    "bengaluru india": ("Bengaluru", "India"),
    "chennai": ("Chennai", "India"),
    "chennai, india": ("Chennai", "India"),
    "hyderabad": ("Hyderabad", "India"),
    "hyderabad, india": ("Hyderabad", "India"),
    "pune": ("Pune", "India"),
    "pune, india": ("Pune", "India"),
    "mumbai": ("Mumbai", "India"),
    "mumbai, india": ("Mumbai", "India"),
    "delhi": ("Delhi NCR", "India"),
    "delhi ncr": ("Delhi NCR", "India"),
    "new delhi": ("Delhi NCR", "India"),
    "new delhi, india": ("Delhi NCR", "India"),
    "gurugram": ("Delhi NCR", "India"),
    "gurgaon": ("Delhi NCR", "India"),
    "noida": ("Delhi NCR", "India"),
    "noida, india": ("Delhi NCR", "India"),
    "san francisco": ("San Francisco", "United States"),
    "new york": ("New York", "United States"),
    "london": ("London", "United Kingdom"),
    "berlin": ("Berlin", "Germany"),
    "toronto": ("Toronto", "Canada"),
    "singapore": ("Singapore", "Singapore"),
    "tokyo": ("Tokyo", "Japan"),
}

# ── Country aliases ─────────────────────────────────────────────────────────

_COUNTRY_ALIASES: dict[str, str] = {
    "india": "India",
    "united states": "United States",
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "germany": "Germany",
    "canada": "Canada",
    "australia": "Australia",
    "japan": "Japan",
    "singapore": "Singapore",
    "europe": "Europe",
}

# ── Remote/worldwide/hybrid keywords ────────────────────────────────────────

_REMOTE_KEYWORDS = {"remote", "work from home", "wfh", "distributed", "anywhere"}
_WORLDWIDE_KEYWORDS = {"worldwide", "global", "anywhere in the world", "world-wide"}
_HYBRID_KEYWORDS = {"hybrid", "hybrid remote", "partially remote"}
_ONSITE_KEYWORDS = {"onsite", "on-site", "in-office", "office", "in office"}


def _strip_location_prefix(text: str) -> str:
    """Remove prefixes like 'Remote -', 'Remote:', etc."""
    text = re.sub(r"^(remote\s*[-–—:]\s*)", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_city_country(raw: str) -> tuple[str | None, str | None]:
    """Try to extract city and country from a location string."""
    # Check exact alias first
    lower = raw.lower().strip()
    if lower in _CITY_ALIASES:
        return _CITY_ALIASES[lower]

    # Try comma-separated "City, Country"
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) == 2:
        city_part, country_part = parts
        city_lower = city_part.lower()
        country_lower = country_part.lower()

        # Check city alias
        if city_lower in _CITY_ALIASES:
            return _CITY_ALIASES[city_lower]

        # Check country alias
        country = _COUNTRY_ALIASES.get(country_lower, country_part.title())
        return city_part.title(), country

    # Single value — might be just a city or country
    if lower in _CITY_ALIASES:
        return _CITY_ALIASES[lower]
    if lower in _COUNTRY_ALIASES:
        return None, _COUNTRY_ALIASES[lower]

    # Return as-is (could be a city name we don't know about)
    return raw.title(), None


def analyze_location(raw_location: str | None) -> LocationInfo:
    """Analyze a raw location string into structured fields.

    Returns a LocationInfo with deterministic, normalized fields.
    Does NOT fabricate data — missing information produces None.
    """
    if not raw_location or not raw_location.strip():
        return LocationInfo(
            raw=raw_location,
            normalized=None,
            city=None,
            country=None,
            is_remote=False,
            is_worldwide=False,
            is_hybrid=False,
            is_onsite=False,
        )

    raw = raw_location.strip()
    lower = raw.lower()

    # Check for remote/worldwide/hybrid flags
    is_remote = any(kw in lower for kw in _REMOTE_KEYWORDS)
    is_worldwide = any(kw in lower for kw in _WORLDWIDE_KEYWORDS)
    is_hybrid = any(kw in lower for kw in _HYBRID_KEYWORDS)
    is_onsite = any(kw in lower for kw in _ONSITE_KEYWORDS)

    # If it's purely a remote/worldwide designation
    pure_remote = is_remote and not any(
        c.isalpha() and c not in "remote -–—:workfromhomefhdistributedanywhere"
        for c in lower.replace("remote", "").replace("-", "").strip()
    )
    pure_worldwide = is_worldwide and not any(
        c.isalpha() and c not in "worldwideglobalanywhereintheworldworld-wide"
        for c in lower.replace("worldwide", "").replace("global", "").strip()
    )

    if pure_remote:
        normalized = "Remote"
        city, country = None, None
    elif pure_worldwide:
        normalized = "Worldwide"
        city, country = None, None
    elif is_hybrid and not any(
        c.isalpha() and c not in "hybridpartiallyremot"
        for c in lower.replace("hybrid", "").strip()
    ):
        normalized = "Hybrid"
        city, country = None, None
    else:
        # Extract city/country from the (possibly remote-flagged) string
        cleaned = _strip_location_prefix(lower)
        cleaned = re.sub(r"\s*\(remote\)\s*", "", cleaned).strip()
        cleaned = re.sub(r"\s*\bhybrid\b\s*", "", cleaned).strip()

        if cleaned:
            city, country = _extract_city_country(cleaned)
        else:
            city, country = None, None

        # Build normalized string
        parts = []
        if city:
            parts.append(city)
        if country:
            parts.append(country)
        normalized = ", ".join(parts) if parts else raw.title()

        if is_remote:
            normalized += " (Remote)"

    return LocationInfo(
        raw=raw_location,
        normalized=normalized,
        city=city,
        country=country,
        is_remote=is_remote,
        is_worldwide=is_worldwide,
        is_hybrid=is_hybrid,
        is_onsite=is_onsite,
    )
