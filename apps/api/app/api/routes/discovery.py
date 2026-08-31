from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.discovery.metadata import (
    SourceMetadata,
    get_source_metadata,
    list_source_metadata,
)
from app.discovery.models import IngestionResult, RawOpportunity
from app.discovery.normalizer import normalize_all
from app.discovery.registry import is_auth_required, list_active_source_names, list_source_names
from app.services.discovery import (
    EnrichedDiscoveryResult,
    discover_enriched,
    ingest,
    run_source,
)

router = APIRouter(
    prefix="/discovery",
    tags=["discovery"],
)


# ── Schemas ────────────────────────────────────────────────────────────────


class SourceListResponse(BaseModel):
    sources: list[str]


class SourceMetadataResponse(BaseModel):
    name: str
    display_name: str
    source_type: str
    description: str
    requires_auth: bool
    enabled: bool
    geographic_coverage: list[str]
    supported_types: list[str]
    supports_remote: bool
    supports_deadline: bool
    supports_salary: bool
    rate_limit_note: str
    source_url: str
    adapter_available: bool


class SourceMetadataListResponse(BaseModel):
    sources: list[SourceMetadataResponse]
    active_count: int
    total_count: int
    auth_required_count: int


class DiscoveryHealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unavailable"
    active_sources: list[str]
    auth_required_sources: list[str]
    total_sources: int


class EnrichedSkillInfo(BaseModel):
    name: str


class EnrichedLocationInfo(BaseModel):
    raw: str | None = None
    normalized: str | None = None
    city: str | None = None
    country: str | None = None
    is_remote: bool = False
    is_worldwide: bool = False
    is_hybrid: bool = False
    is_onsite: bool = False


class EnrichedOpportunityResponse(BaseModel):
    source_name: str
    external_id: str | None = None
    canonical_source_url: str | None = None
    normalized_title: str
    normalized_company_name: str
    description: str | None = None
    opportunity_type: str
    normalized_location: str | None = None
    is_remote: bool = False
    is_worldwide: bool = False
    city: str | None = None
    country: str | None = None
    category: str | None = None
    extracted_skills: list[str] = []
    deadline: Any = None


class EnrichedDiscoveryResponse(BaseModel):
    source_name: str
    raw_count: int
    enriched_count: int
    remote_count: int = 0
    worldwide_count: int = 0
    countries: list[str] = []
    categories: list[str] = []
    all_skills: list[str] = []
    errors: list[str] = []
    opportunities: list[EnrichedOpportunityResponse] = []


# ── Manual raw ingestion ──────────────────────────────────────────────────


@router.post(
    "/run",
    response_model=IngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest raw opportunity records (manual)",
    description=(
        "Accept a batch of raw opportunity records, normalize them, "
        "deduplicate, resolve companies, and persist new opportunities. "
        "This endpoint does not perform any external fetching — the caller "
        "provides the raw data."
    ),
)
def run_discovery(
    raw_items: list[RawOpportunity],
    db: Session = Depends(get_db),
) -> IngestionResult:
    normalized = normalize_all(raw_items)
    return ingest(db, normalized)


# ── Source listing (simple) ────────────────────────────────────────────────


@router.get(
    "/sources",
    response_model=SourceListResponse,
    summary="List available discovery sources",
    description="Returns the names of all registered source adapters.",
)
def list_sources() -> SourceListResponse:
    return SourceListResponse(sources=list_source_names())


# ── Source metadata (rich) ─────────────────────────────────────────────────


@router.get(
    "/sources/metadata",
    response_model=SourceMetadataListResponse,
    summary="List sources with rich metadata",
    description=(
        "Returns detailed metadata for all registered sources including "
        "capabilities, coverage, authentication requirements, and adapter status."
    ),
)
def list_sources_metadata() -> SourceMetadataListResponse:
    all_meta = list_source_metadata()
    active = list_active_source_names()
    auth_required = [m.name for m in all_meta if m.requires_auth]

    return SourceMetadataListResponse(
        sources=[
            SourceMetadataResponse(**m.to_dict())
            for m in all_meta
        ],
        active_count=len(active),
        total_count=len(all_meta),
        auth_required_count=len(auth_required),
    )


@router.get(
    "/sources/{source_name}/metadata",
    response_model=SourceMetadataResponse,
    summary="Get metadata for a specific source",
)
def get_source_metadata_endpoint(source_name: str) -> SourceMetadataResponse:
    meta = get_source_metadata(source_name)
    if meta is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source '{source_name}' not found",
        )
    return SourceMetadataResponse(**meta.to_dict())


# ── Discovery health ───────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=DiscoveryHealthResponse,
    summary="Discovery system health",
    description="Returns the health status of the discovery system and source adapters.",
)
def discovery_health() -> DiscoveryHealthResponse:
    all_names = list_source_names()
    active = list_active_source_names()
    auth_required = [n for n in all_names if is_auth_required(n)]

    if active:
        health_status = "healthy"
    elif auth_required and not active:
        health_status = "unavailable"
    else:
        health_status = "degraded"

    return DiscoveryHealthResponse(
        status=health_status,
        active_sources=active,
        auth_required_sources=auth_required,
        total_sources=len(all_names),
    )


# ── Source-driven discovery (ingest) ──────────────────────────────────────


@router.post(
    "/run/{source}",
    response_model=IngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Run a registered source adapter",
    description=(
        "Invoke a registered source adapter by name. The adapter fetches "
        "opportunities from the external source, normalizes them, and "
        "ingests them into the database. No external API keys are required "
        "for public sources."
    ),
)
def run_source_discovery(
    source: str,
    db: Session = Depends(get_db),
) -> IngestionResult:
    return run_source(db, source)


# ── Enriched discovery (preview, no persistence) ──────────────────────────


@router.get(
    "/sources/{source_name}/preview",
    response_model=EnrichedDiscoveryResponse,
    summary="Preview enriched discovery results (no persistence)",
    description=(
        "Fetch opportunities from a source and return enriched data "
        "including location intelligence, skill extraction, and type "
        "classification. Does NOT persist any data."
    ),
)
def preview_source(source_name: str) -> EnrichedDiscoveryResponse:
    result = discover_enriched(source_name)

    opportunities = []
    for item in result.enriched_items:
        loc_info = item.location_info
        opportunities.append(
            EnrichedOpportunityResponse(
                source_name=item.source_name,
                external_id=item.external_id,
                canonical_source_url=item.canonical_source_url,
                normalized_title=item.normalized_title,
                normalized_company_name=item.normalized_company_name,
                description=item.description[:500] if item.description else None,
                opportunity_type=item.opportunity_type,
                normalized_location=item.normalized_location,
                is_remote=item.is_remote,
                is_worldwide=item.is_worldwide,
                city=item.city,
                country=item.country,
                category=item.category,
                extracted_skills=sorted(item.extracted_skills),
                deadline=item.deadline,
            )
        )

    return EnrichedDiscoveryResponse(
        source_name=result.source_name,
        raw_count=result.raw_count,
        enriched_count=result.enriched_count,
        remote_count=result.remote_count,
        worldwide_count=result.worldwide_count,
        countries=result.countries,
        categories=result.categories,
        all_skills=result.all_skills,
        errors=result.errors,
        opportunities=opportunities,
    )
