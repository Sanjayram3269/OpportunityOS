"""Enhanced planning intelligence — campaign-aware and application-aware planning.

Extends the existing planning service with:
- Campaign-aware priority boosting
- Application-aware planning context
- Outreach-aware planning state
- Follow-up-aware planning state
- Campaign grouping for planning overview

All calculations remain deterministic and explainable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.campaign import Campaign
from app.models.campaign_opportunity import CampaignOpportunity
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.planning import (
    HORIZON_FUTURE,
    HORIZON_NOW,
    HORIZON_SUMMER_2027,
    HORIZON_UNKNOWN,
    HORIZON_UPCOMING,
    calculate_planning_priority,
    classify_horizon,
)

logger = logging.getLogger(__name__)


def get_enhanced_planning_data(
    db: Session,
    *,
    horizon: str | None = None,
    min_match_score: int | None = None,
    opp_type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    campaign_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get planning data enriched with application, outreach, and campaign context.

    Returns a list of planning info dicts with:
    - Planning horizon and priority
    - Application status
    - Outreach status
    - Follow-up status
    - Campaign membership
    """
    now = datetime.now(timezone.utc)

    # Build base query
    stmt = select(Opportunity)

    if opp_type is not None:
        stmt = stmt.where(Opportunity.type == opp_type)
    if status is not None:
        stmt = stmt.where(Opportunity.status == status)
    if priority is not None:
        stmt = stmt.where(Opportunity.priority == priority)
    if min_match_score is not None:
        stmt = stmt.where(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= min_match_score,
        )

    # Filter by campaign if specified
    if campaign_id is not None:
        stmt = stmt.join(
            CampaignOpportunity,
            CampaignOpportunity.opportunity_id == Opportunity.id,
        ).where(CampaignOpportunity.campaign_id == campaign_id)

    opportunities = list(db.scalars(stmt))

    # Pre-fetch application, message, follow-up, and campaign data for efficiency
    opp_ids = [opp.id for opp in opportunities]

    # Batch fetch applications
    app_map: dict[int, Application] = {}
    if opp_ids:
        apps = db.query(Application).filter(Application.opportunity_id.in_(opp_ids)).all()
        for app in apps:
            app_map[app.opportunity_id] = app

    # Batch fetch message statuses
    msg_status_map: dict[int, dict[str, int]] = {}
    if opp_ids:
        msg_results = (
            db.query(Message.opportunity_id, Message.status, func.count(Message.id))
            .filter(Message.opportunity_id.in_(opp_ids))
            .group_by(Message.opportunity_id, Message.status)
            .all()
        )
        for opp_id, status_val, count in msg_results:
            if opp_id not in msg_status_map:
                msg_status_map[opp_id] = {}
            msg_status_map[opp_id][status_val] = count

    # Batch fetch follow-up statuses
    fu_status_map: dict[int, dict[str, int]] = {}
    if opp_ids:
        fu_results = (
            db.query(FollowUp.opportunity_id, FollowUp.status, func.count(FollowUp.id))
            .filter(FollowUp.opportunity_id.in_(opp_ids))
            .group_by(FollowUp.opportunity_id, FollowUp.status)
            .all()
        )
        for opp_id, status_val, count in fu_results:
            if opp_id not in fu_status_map:
                fu_status_map[opp_id] = {}
            fu_status_map[opp_id][status_val] = count

    # Batch fetch campaign memberships
    campaign_map: dict[int, list[str]] = {}
    if opp_ids:
        camp_results = (
            db.query(CampaignOpportunity.opportunity_id, Campaign.name)
            .join(Campaign, Campaign.id == CampaignOpportunity.campaign_id)
            .filter(CampaignOpportunity.opportunity_id.in_(opp_ids))
            .all()
        )
        for opp_id, campaign_name in camp_results:
            if opp_id not in campaign_map:
                campaign_map[opp_id] = []
            campaign_map[opp_id].append(campaign_name)

    # Build enriched results
    results = []
    for opp in opportunities:
        company = db.get(Company, opp.company_id)
        company_name = company.name if company else None

        hz = classify_horizon(opp.deadline, now)

        if horizon is not None and hz != horizon:
            continue

        # Application context
        app = app_map.get(opp.id)
        app_status = app.status if app else "NOT_APPLIED"

        # Outreach context
        msg_statuses = msg_status_map.get(opp.id, {})
        has_draft = msg_statuses.get("DRAFT", 0) > 0
        has_pending_approval = msg_statuses.get("PENDING_APPROVAL", 0) > 0
        has_ready_to_send = msg_statuses.get("READY_TO_SEND", 0) > 0
        has_sent = msg_statuses.get("SENT", 0) > 0

        # Follow-up context
        fu_statuses = fu_status_map.get(opp.id, {})
        has_due_followup = fu_statuses.get("DUE", 0) > 0
        has_pending_followup = fu_statuses.get("PENDING", 0) > 0

        # Campaign context
        campaign_names = campaign_map.get(opp.id, [])

        # Build outreach status
        outreach_status = _derive_outreach_status(
            has_draft, has_pending_approval, has_ready_to_send, has_sent
        )

        # Build follow-up status
        followup_status = _derive_followup_status(
            has_due_followup, has_pending_followup
        )

        # Build explanation
        explanation = _build_enhanced_explanation(
            match_score=opp.match_score,
            horizon=hz,
            app_status=app_status,
            outreach_status=outreach_status,
            followup_status=followup_status,
            campaign_names=campaign_names,
        )

        results.append({
            "opportunity_id": opp.id,
            "title": opp.title,
            "company_name": company_name,
            "opportunity_type": opp.type,
            "status": opp.status,
            "priority": opp.priority,
            "deadline": opp.deadline,
            "match_score": opp.match_score,
            "planning_horizon": hz,
            "application_status": app_status,
            "outreach_status": outreach_status,
            "followup_status": followup_status,
            "campaigns": campaign_names,
            "planning_explanation": explanation,
        })

    # Sort by match_score descending (higher = more actionable)
    results.sort(
        key=lambda r: (
            -(r["match_score"] or 0),
            r["opportunity_id"],
        )
    )

    return results[:limit]


def get_planning_overview_summary(db: Session) -> dict:
    """Get a summary overview of the planning landscape.

    Returns counts by horizon, application status, and overall metrics.
    """
    now = datetime.now(timezone.utc)

    opportunities = db.query(Opportunity).all()

    horizon_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    total_match_score = 0
    scored_count = 0

    for opp in opportunities:
        horizon = classify_horizon(opp.deadline, now)
        horizon_counts[horizon] = horizon_counts.get(horizon, 0) + 1
        type_counts[opp.type] = type_counts.get(opp.type, 0) + 1
        if opp.match_score is not None:
            total_match_score += opp.match_score
            scored_count += 1

    # Application stats
    app_status_counts = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    total_opportunities = len(opportunities)
    total_applications = sum(app_status_counts.values())
    not_applied = total_opportunities - total_applications

    return {
        "total_opportunities": total_opportunities,
        "total_applications": total_applications,
        "not_applied": not_applied,
        "average_match_score": round(total_match_score / scored_count, 1) if scored_count > 0 else None,
        "horizon_distribution": horizon_counts,
        "type_distribution": type_counts,
        "application_status_distribution": app_status_counts,
    }


def _derive_outreach_status(
    has_draft: bool,
    has_pending_approval: bool,
    has_ready_to_send: bool,
    has_sent: bool,
) -> str:
    """Derive outreach status from message state."""
    if has_ready_to_send:
        return "READY_TO_SEND"
    if has_pending_approval:
        return "PENDING_APPROVAL"
    if has_draft:
        return "DRAFT"
    if has_sent:
        return "SENT"
    return "NO_OUTREACH"


def _derive_followup_status(
    has_due_followup: bool,
    has_pending_followup: bool,
) -> str:
    """Derive follow-up status from follow-up state."""
    if has_due_followup:
        return "DUE"
    if has_pending_followup:
        return "PENDING"
    return "NO_FOLLOWUP"


def _build_enhanced_explanation(
    *,
    match_score: int | None,
    horizon: str,
    app_status: str,
    outreach_status: str,
    followup_status: str,
    campaign_names: list[str],
) -> str:
    """Build a deterministic explanation string."""
    parts = []

    if match_score is not None:
        if match_score >= 80:
            parts.append(f"High match ({match_score}/100)")
        elif match_score >= 60:
            parts.append(f"Moderate match ({match_score}/100)")
        else:
            parts.append(f"Lower match ({match_score}/100)")
    else:
        parts.append("Match not scored")

    if horizon == HORIZON_SUMMER_2027:
        parts.append("Summer 2027 target")
    elif horizon == HORIZON_NOW:
        parts.append("Deadline imminent")
    elif horizon == HORIZON_UPCOMING:
        parts.append("Upcoming deadline")

    if app_status == "NOT_APPLIED":
        parts.append("not yet applied")
    elif app_status in ("INTERVIEW", "FINAL_ROUND"):
        parts.append(f"in {app_status.lower().replace('_', ' ')}")
    elif app_status == "OFFER":
        parts.append("received offer")
    elif app_status in ("ACCEPTED",):
        parts.append("accepted")
    elif app_status in ("REJECTED", "WITHDRAWN"):
        parts.append(f"application {app_status.lower()}")

    if outreach_status == "NO_OUTREACH":
        pass  # Don't mention if no outreach
    elif outreach_status == "READY_TO_SEND":
        parts.append("outreach ready to send")
    elif outreach_status == "PENDING_APPROVAL":
        parts.append("outreach awaiting approval")
    elif outreach_status == "SENT":
        parts.append("outreach sent")

    if followup_status == "DUE":
        parts.append("follow-up due")
    elif followup_status == "PENDING":
        parts.append("follow-up scheduled")

    if campaign_names:
        parts.append(f"in campaign: {', '.join(campaign_names[:2])}")

    return ". ".join(parts) + "."
