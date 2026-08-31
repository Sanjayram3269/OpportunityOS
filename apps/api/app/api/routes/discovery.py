from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.discovery.models import IngestionResult, RawOpportunity
from app.discovery.normalizer import normalize_all
from app.discovery.registry import list_source_names
from app.services.discovery import ingest, run_source

router = APIRouter(
    prefix="/discovery",
    tags=["discovery"],
)


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


# ── Source-driven discovery ───────────────────────────────────────────────


class SourceListResponse(BaseModel):
    sources: list[str]


@router.get(
    "/sources",
    response_model=SourceListResponse,
    summary="List available discovery sources",
    description="Returns the names of all registered source adapters.",
)
def list_sources() -> SourceListResponse:
    return SourceListResponse(sources=list_source_names())


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
