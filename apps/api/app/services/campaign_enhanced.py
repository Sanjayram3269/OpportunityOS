"""Enhanced campaign intelligence — application-aware summaries and planning integration.

Extends the existing campaign service with:
- Application status breakdowns within campaigns
- Action status breakdowns within campaigns
- Planning horizon distribution for campaign opportunities
- Campaign-aware planning priority boosting
- Deterministic campaign intelligence

All values are derived from source-of-truth records.
No fabricated statistics.
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
from app.services.campaign import list_opportunity_campaigns
from app.services.planning import classify_horizon

logger = logging.getLogger(__name__)


def get_enhanced_campaign_summary(db: Session, campaign: Campaign) -> dict:
    """Build a comprehensive campaign summary with application/action breakdowns.

    Returns a dict containing:
    - Basic counts (opportunities, match scores)
    - Application status breakdown
    - Message status breakdown
    - Follow-up status breakdown
    - Action status breakdown
    - Planning horizon distribution
    """
    now = datetime.now(timezone.utc)

    # Get opportunity IDs in this campaign
    opp_ids = list(
        db.scalars(
            select(CampaignOpportunity.opportunity_id).where(
                CampaignOpportunity.campaign_id == campaign.id
            )
        )
    )

    total_opportunities = len(opp_ids)

    # ── Match score statistics ────────────────────────────────
    avg_score = None
    high_match_count = 0
    if opp_ids:
        scores = list(
            db.scalars(
                select(Opportunity.match_score).where(
                    Opportunity.id.in_(opp_ids),
                    Opportunity.match_score.isnot(None),
                )
            )
        )
        if scores:
            avg_score = float(sum(scores)) / len(scores)
            high_match_count = sum(1 for s in scores if s >= 80)

    # ── Application status breakdown ──────────────────────────
    app_status_counts: dict[str, int] = {}
    if opp_ids:
        results = (
            db.query(Application.status, func.count(Application.id))
            .join(Opportunity, Application.opportunity_id == Opportunity.id)
            .filter(Application.opportunity_id.in_(opp_ids))
            .group_by(Application.status)
            .all()
        )
        app_status_counts = {status: count for status, count in results}

    total_applications = sum(app_status_counts.values())
    interviews = app_status_counts.get("INTERVIEW", 0) + app_status_counts.get("FINAL_ROUND", 0)
    offers = app_status_counts.get("OFFER", 0) + app_status_counts.get("ACCEPTED", 0)
    rejections = app_status_counts.get("REJECTED", 0)
    not_applied_count = total_opportunities - total_applications

    # ── Message status breakdown ──────────────────────────────
    msg_status_counts: dict[str, int] = {}
    if opp_ids:
        results = (
            db.query(Message.status, func.count(Message.id))
            .filter(Message.opportunity_id.in_(opp_ids))
            .group_by(Message.status)
            .all()
        )
        msg_status_counts = {status: count for status, count in results}

    # ── Follow-up status breakdown ────────────────────────────
    fu_status_counts: dict[str, int] = {}
    if opp_ids:
        results = (
            db.query(FollowUp.status, func.count(FollowUp.id))
            .filter(FollowUp.opportunity_id.in_(opp_ids))
            .group_by(FollowUp.status)
            .all()
        )
        fu_status_counts = {status: count for status, count in results}

    followups_pending = sum(
        fu_status_counts.get(s, 0)
        for s in ("PENDING", "DUE", "PENDING_APPROVAL", "APPROVED", "READY_TO_SEND")
    )
    followups_completed = fu_status_counts.get("COMPLETED", 0)
    followups_overdue = fu_status_counts.get("DUE", 0)

    # ── Planning horizon distribution ─────────────────────────
    horizon_counts: dict[str, int] = {}
    if opp_ids:
        opportunities = db.query(Opportunity).filter(Opportunity.id.in_(opp_ids)).all()
        for opp in opportunities:
            horizon = classify_horizon(opp.deadline, now)
            horizon_counts[horizon] = horizon_counts.get(horizon, 0) + 1

    # ── Build response ────────────────────────────────────────
    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "total_opportunities": total_opportunities,
        "average_match_score": round(avg_score, 1) if avg_score else None,
        "high_match_count": high_match_count,
        # Application status
        "applications_started": total_applications,
        "applications_submitted": sum(
            app_status_counts.get(s, 0)
            for s in ("APPLIED", "ASSESSMENT", "INTERVIEW", "FINAL_ROUND", "OFFER", "ACCEPTED")
        ),
        "interviews": interviews,
        "offers": offers,
        "rejections": rejections,
        "not_applied": not_applied_count,
        "application_status_breakdown": app_status_counts,
        # Message status
        "drafts_count": msg_status_counts.get("DRAFT", 0),
        "pending_approval_count": msg_status_counts.get("PENDING_APPROVAL", 0),
        "approved_count": msg_status_counts.get("APPROVED", 0),
        "sent_count": msg_status_counts.get("SENT", 0),
        # Follow-ups
        "followups_pending": followups_pending,
        "followups_completed": followups_completed,
        "followups_overdue": followups_overdue,
        "followups_cancelled": fu_status_counts.get("CANCELLED", 0),
        # Planning distribution
        "planning_horizon_distribution": horizon_counts,
    }


def get_campaign_planning_data(
    db: Session,
    campaign: Campaign,
    *,
    horizon: str | None = None,
    min_match_score: int | None = None,
) -> list[dict]:
    """Get planning data for opportunities within a specific campaign.

    Returns planning data enriched with campaign context.
    Uses batched queries to avoid N+1.
    """
    now = datetime.now(timezone.utc)

    # Get opportunities in campaign
    stmt = (
        select(Opportunity)
        .join(CampaignOpportunity, CampaignOpportunity.opportunity_id == Opportunity.id)
        .where(CampaignOpportunity.campaign_id == campaign.id)
    )

    if min_match_score is not None:
        stmt = stmt.where(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= min_match_score,
        )

    opportunities = list(db.scalars(stmt))

    if not opportunities:
        return []

    opp_ids = [opp.id for opp in opportunities]
    company_ids = {opp.company_id for opp in opportunities}

    # Batch fetch companies
    company_map: dict[int, str | None] = {}
    if company_ids:
        companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
        company_map = {c.id: c.name for c in companies}

    # Batch fetch applications
    app_map: dict[int, str] = {}
    if opp_ids:
        apps = db.query(Application).filter(Application.opportunity_id.in_(opp_ids)).all()
        app_map = {a.opportunity_id: a.status for a in apps}

    # Batch fetch campaign memberships for other campaigns
    campaign_map: dict[int, list[str]] = {}
    if opp_ids:
        camp_results = (
            db.query(CampaignOpportunity.opportunity_id, Campaign.name)
            .join(Campaign, Campaign.id == CampaignOpportunity.campaign_id)
            .filter(
                CampaignOpportunity.opportunity_id.in_(opp_ids),
                CampaignOpportunity.campaign_id != campaign.id,
            )
            .all()
        )
        for opp_id, campaign_name in camp_results:
            if opp_id not in campaign_map:
                campaign_map[opp_id] = []
            campaign_map[opp_id].append(campaign_name)

    # Build results
    results = []
    for opp in opportunities:
        company_name = company_map.get(opp.company_id)

        hz = classify_horizon(opp.deadline, now)

        if horizon is not None and hz != horizon:
            continue

        app_status = app_map.get(opp.id, "NOT_APPLIED")
        campaign_names = campaign_map.get(opp.id, [])

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
            "other_campaigns": campaign_names,
        })

    return results


def get_campaign_action_summary(db: Session, campaign: Campaign) -> dict:
    """Get action items related to opportunities in this campaign.

    Returns counts of open actions by type and priority for
    opportunities within the campaign.
    """
    from app.models.application import Action

    opp_ids = list(
        db.scalars(
            select(CampaignOpportunity.opportunity_id).where(
                CampaignOpportunity.campaign_id == campaign.id
            )
        )
    )

    if not opp_ids:
        return {
            "total_actions": 0,
            "by_priority": {},
            "by_type": {},
            "overdue_actions": 0,
        }

    # Count actions for opportunities in this campaign
    action_stats = (
        db.query(Action.priority, Action.action_type, func.count(Action.id))
        .filter(
            Action.entity_type == "opportunity",
            Action.entity_id.in_(opp_ids),
            Action.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .group_by(Action.priority, Action.action_type)
        .all()
    )

    by_priority: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total = 0

    for priority, action_type, count in action_stats:
        by_priority[priority] = by_priority.get(priority, 0) + count
        by_type[action_type] = by_type.get(action_type, 0) + count
        total += count

    # Count overdue actions
    overdue_count = (
        db.query(func.count(Action.id))
        .filter(
            Action.entity_type == "opportunity",
            Action.entity_id.in_(opp_ids),
            Action.status.in_(["OPEN", "IN_PROGRESS"]),
            Action.due_at.isnot(None),
            Action.due_at < datetime.now(timezone.utc),
        )
        .scalar()
        or 0
    )

    return {
        "total_actions": total,
        "by_priority": by_priority,
        "by_type": by_type,
        "overdue_actions": overdue_count,
    }
