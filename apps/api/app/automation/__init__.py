"""Automation engine — orchestrates discovery, matching, planning, and outreach preparation.

The automation engine ties together existing subsystems into a coherent pipeline:
  discovery → normalization → deduplication → ingestion → matching → planning → AI enrichment → draft preparation

Key safety rules:
- Human approval is ALWAYS required for outreach sending
- AI is optional — deterministic matching is the source of truth
- Automation is idempotent — repeated runs don't create duplicates
- One source failure doesn't stop the entire run
"""
