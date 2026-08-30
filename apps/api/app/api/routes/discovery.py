from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.discovery.models import IngestionResult, RawOpportunity
from app.discovery.normalizer import normalize_all
from app.services.discovery import ingest

router = APIRouter(
    prefix="/discovery",
    tags=["discovery"],
)


@router.post(
    "/run",
    response_model=IngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest raw opportunity records",
    description=(
        "Accept a batch of raw opportunity records, normalize them, "
        "deduplicate, resolve companies, and persist new opportunities. "
        "This endpoint does not perform any external fetching — the caller "
        "provides the raw data. Actual source adapters will be invoked "
        "server-side in a future phase."
    ),
)
def run_discovery(
    raw_items: list[RawOpportunity],
    db: Session = Depends(get_db),
) -> IngestionResult:
    normalized = normalize_all(raw_items)
    return ingest(db, normalized)
