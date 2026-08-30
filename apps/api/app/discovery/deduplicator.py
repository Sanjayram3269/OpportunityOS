from __future__ import annotations

from collections import OrderedDict

from app.discovery.normalizer import NormalizedOpportunity


def _dedupe_key_external_id(item: NormalizedOpportunity) -> str | None:
    """Primary dedup key: source + external_id (most reliable)."""
    if item.external_id is None:
        return None
    return f"{item.source_name}::{item.external_id}"


def _dedupe_key_url(item: NormalizedOpportunity) -> str | None:
    """Secondary dedup key: canonical source URL."""
    if item.canonical_source_url is None:
        return None
    return item.canonical_source_url


def _dedupe_key_company_title(item: NormalizedOpportunity) -> str:
    """Tertiary dedup key: source + normalized company + title.

    This catches duplicates from the same source with the same company and
    role title, even when no external ID or URL is available.  Different
    companies with the same title, or the same company on different sources,
    will NOT be considered duplicates.
    """
    return f"{item.source_name}::{item.normalized_company_name}::{item.normalized_title}"


def deduplicate(items: list[NormalizedOpportunity]) -> list[NormalizedOpportunity]:
    """Remove duplicate opportunities from a batch.

    Deduplication is evaluated in priority order:
      1. ``source + external_id`` — most specific, catches reposts with an ID
      2. ``canonical URL`` — catches same-posting-under-different-IDs
      3. ``company + title`` — catches reposts with no ID/URL

    The first occurrence is always kept.  Deterministic for a given input.
    """
    seen_external: OrderedDict[str, NormalizedOpportunity] = OrderedDict()
    seen_url: OrderedDict[str, NormalizedOpportunity] = OrderedDict()
    seen_company_title: OrderedDict[str, NormalizedOpportunity] = OrderedDict()

    result: list[NormalizedOpportunity] = []

    for item in items:
        # ── Check 1: source + external_id ──────────────────────────────
        ext_key = _dedupe_key_external_id(item)
        if ext_key is not None and ext_key in seen_external:
            continue

        # ── Check 2: canonical URL ─────────────────────────────────────
        url_key = _dedupe_key_url(item)
        if url_key is not None and url_key in seen_url:
            continue

        # ── Check 3: company + title ───────────────────────────────────
        ct_key = _dedupe_key_company_title(item)
        if ct_key in seen_company_title:
            continue

        # ── Not a duplicate — register all keys ────────────────────────
        if ext_key is not None:
            seen_external[ext_key] = item
        if url_key is not None:
            seen_url[url_key] = item
        seen_company_title[ct_key] = item
        result.append(item)

    return result
