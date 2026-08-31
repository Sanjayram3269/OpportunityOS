"""Planning API routes — opportunity time horizon and priority classification.

Endpoints:
    GET /opportunities/planning → List opportunities with planning data

Returns deterministic planning horizon and priority for each opportunity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.planning import PlanningHorizonInfo, PlanningListResponse
from app.services.planning import get_planning_data

router = APIRouter(
    prefix="/opportunities",
    tags=["planning"],
)


@router.get(
    "/planning",
    response_model=PlanningListResponse,
    summary="Opportunity planning overview",
    description=(
        "Returns opportunities with deterministic planning horizon and priority. "
        "Horizons: NOW, UPCOMING, SUMMER_2027, FUTURE, UNKNOWN. "
        "Priority is a separate concept from match_score."
    ),
)
def get_planning_overview(
    horizon: str | None = Query(
        default=None,
        description="Filter by planning horizon (NOW, UPCOMING, SUMMER_2027, FUTURE, UNKNOWN)",
    ),
    min_match_score: int | None = Query(
        default=None,
        ge=0,
        le=100,
        description="Minimum match score filter",
    ),
    type: str | None = Query(default=None, description="Filter by opportunity type"),
    status: str | None = Query(default=None, description="Filter by status"),
    priority: str | None = Query(default=None, description="Filter by priority"),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PlanningListResponse:
    results = get_planning_data(
        db,
        horizon=horizon,
        min_match_score=min_match_score,
        opp_type=type,
        status=status,
        priority=priority,
        limit=limit,
    )

    return PlanningListResponse(
        total=len(results),
        opportunities=[PlanningHorizonInfo(**r) for r in results],
    )
