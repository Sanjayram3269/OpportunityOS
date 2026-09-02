"""Dashboard / Command Center API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dashboard import CommandCenterResponse
from app.services.dashboard import get_command_center

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=CommandCenterResponse)
def dashboard_overview(db: Session = Depends(get_db)):
    """Get the complete command center overview.

    Aggregates real data from:
    - Actions (action center)
    - Applications (lifecycle)
    - Opportunities (discovery/matching)
    - Campaigns
    - Messages (outreach)
    - FollowUps
    - Companies

    Returns actionable operational intelligence.
    """
    return get_command_center(db)
