"""Export API routes — Excel workbook download.

Endpoints:
    GET /exports/opportunities.xlsx → Download full workbook

Read-only. Never modifies database records.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.export.workbook import build_workbook
from app.services.export import ExportOptions, build_export_data

router = APIRouter(
    prefix="/exports",
    tags=["exports"],
)


@router.get(
    "/opportunities.xlsx",
    summary="Export opportunity pipeline as Excel",
    description=(
        "Download a multi-sheet Excel workbook containing Opportunities, "
        "Companies, Leads, Outreach, FollowUps, Campaigns, and Summary. "
        "Supports optional filters."
    ),
)
def export_opportunities(
    planning_horizon: str | None = Query(
        default=None,
        description="Filter by planning horizon (NOW, UPCOMING, SUMMER_2027, FUTURE, UNKNOWN)",
    ),
    min_match_score: int | None = Query(
        default=None, ge=0, le=100,
        description="Minimum match score filter",
    ),
    opportunity_type: str | None = Query(
        default=None,
        description="Filter by opportunity type",
    ),
    status: str | None = Query(
        default=None,
        description="Filter by opportunity status",
    ),
    priority: str | None = Query(
        default=None,
        description="Filter by opportunity priority",
    ),
    campaign_id: int | None = Query(
        default=None,
        description="Filter by campaign membership",
    ),
    company_id: int | None = Query(
        default=None,
        description="Filter by company",
    ),
    location: str | None = Query(
        default=None,
        description="Filter by company location (case-insensitive substring)",
    ),
    db: Session = Depends(get_db),
):
    opts = ExportOptions(
        planning_horizon=planning_horizon,
        min_match_score=min_match_score,
        opportunity_type=opportunity_type,
        status=status,
        priority=priority,
        campaign_id=campaign_id,
        company_id=company_id,
        location=location,
    )

    data = build_export_data(db, opts)
    buf = build_workbook(data)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="opportunities.xlsx"',
        },
    )
