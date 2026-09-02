"""Dashboard / Command Center service — aggregates operational data.

Provides a single authoritative overview of the entire opportunity pipeline.
All values derived from source-of-truth PostgreSQL records.

Sections:
- overview: total counts, key metrics
- today: actions due today, overdue items
- upcoming: deadlines in next 7 days, follow-ups due
- pipeline: application status breakdown
- opportunities: opportunity metrics, match score distribution
- summer_2027: Summer 2027 specific metrics
- campaigns: campaign status and activity
- outreach: message status breakdown
- followups: follow-up status breakdown
- analytics: conversion rates, source performance, campaign performance

NO fabricated data. NO hardcoded metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Action, Application
from app.models.campaign import Campaign
from app.models.campaign_opportunity import CampaignOpportunity
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.planning import classify_horizon

logger = logging.getLogger(__name__)

# Application status groups
_ACTIVE_APP_STATUSES = {
    "NOT_APPLIED", "READY", "APPLIED", "ASSESSMENT",
    "INTERVIEW", "FINAL_ROUND", "OFFER",
}
_TERMINAL_APP_STATUSES = {"ACCEPTED", "REJECTED", "WITHDRAWN"}

# Action statuses
ACTION_OPEN = "OPEN"
ACTION_IN_PROGRESS = "IN_PROGRESS"
ACTION_COMPLETED = "COMPLETED"
ACTION_DISMISSED = "DISMISSED"
ACTION_EXPIRED = "EXPIRED"


def get_command_center(db: Session) -> dict:
    """Get the complete command center overview.

    Returns a dict with all dashboard sections.
    Each section is independently useful — failures in one section
    do not prevent other sections from being returned.
    """
    now = datetime.now(timezone.utc)

    result: dict = {}

    try:
        result["overview"] = _get_overview(db, now)
    except Exception as exc:
        logger.error("Dashboard overview failed: %s", exc)
        result["overview"] = _empty_overview()

    try:
        result["today"] = _get_today(db, now)
    except Exception as exc:
        logger.error("Dashboard today failed: %s", exc)
        result["today"] = _empty_today()

    try:
        result["pipeline"] = _get_pipeline(db, now)
    except Exception as exc:
        logger.error("Dashboard pipeline failed: %s", exc)
        result["pipeline"] = _empty_pipeline()

    try:
        result["opportunities"] = _get_opportunities(db, now)
    except Exception as exc:
        logger.error("Dashboard opportunities failed: %s", exc)
        result["opportunities"] = _empty_opportunities()

    try:
        result["summer_2027"] = _get_summer_2027(db, now)
    except Exception as exc:
        logger.error("Dashboard summer_2027 failed: %s", exc)
        result["summer_2027"] = _empty_summer_2027()

    try:
        result["campaigns"] = _get_campaigns(db, now)
    except Exception as exc:
        logger.error("Dashboard campaigns failed: %s", exc)
        result["campaigns"] = _empty_campaigns()

    try:
        result["outreach"] = _get_outreach(db)
    except Exception as exc:
        logger.error("Dashboard outreach failed: %s", exc)
        result["outreach"] = _empty_outreach()

    try:
        result["followups"] = _get_followups(db, now)
    except Exception as exc:
        logger.error("Dashboard followups failed: %s", exc)
        result["followups"] = _empty_followups()

    try:
        result["analytics"] = _get_analytics(db, now)
    except Exception as exc:
        logger.error("Dashboard analytics failed: %s", exc)
        result["analytics"] = _empty_analytics()

    return result


# ── Overview ──────────────────────────────────────────────────────────


def _get_overview(db: Session, now: datetime) -> dict:
    """Top-level summary counts."""
    total_opps = db.query(func.count(Opportunity.id)).scalar() or 0
    total_apps = db.query(func.count(Application.id)).scalar() or 0
    total_actions = db.query(func.count(Action.id)).scalar() or 0
    open_actions = (
        db.query(func.count(Action.id))
        .filter(Action.status.in_([ACTION_OPEN, ACTION_IN_PROGRESS]))
        .scalar()
        or 0
    )
    total_campaigns = db.query(func.count(Campaign.id)).scalar() or 0
    active_campaigns = (
        db.query(func.count(Campaign.id))
        .filter(Campaign.status == "ACTIVE")
        .scalar()
        or 0
    )
    high_match = (
        db.query(func.count(Opportunity.id))
        .filter(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 80,
        )
        .scalar()
        or 0
    )

    return {
        "total_opportunities": total_opps,
        "total_applications": total_apps,
        "open_actions": open_actions,
        "total_actions": total_actions,
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "high_match_opportunities": high_match,
    }


# ── Today ─────────────────────────────────────────────────────────────


def _get_today(db: Session, now: datetime) -> dict:
    """Actions and deadlines for today/overdue."""
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Overdue actions
    overdue_actions = (
        db.query(func.count(Action.id))
        .filter(
            Action.status.in_([ACTION_OPEN, ACTION_IN_PROGRESS]),
            Action.due_at.isnot(None),
            Action.due_at < today_start,
        )
        .scalar()
        or 0
    )

    # Actions due today
    today_end = today_start + timedelta(days=1)
    due_today = (
        db.query(func.count(Action.id))
        .filter(
            Action.status.in_([ACTION_OPEN, ACTION_IN_PROGRESS]),
            Action.due_at.isnot(None),
            Action.due_at >= today_start,
            Action.due_at < today_end,
        )
        .scalar()
        or 0
    )

    # P0 actions
    p0_actions = (
        db.query(func.count(Action.id))
        .filter(
            Action.status == ACTION_OPEN,
            Action.priority == "P0",
        )
        .scalar()
        or 0
    )

    # P1 actions
    p1_actions = (
        db.query(func.count(Action.id))
        .filter(
            Action.status == ACTION_OPEN,
            Action.priority == "P1",
        )
        .scalar()
        or 0
    )

    # Overdue deadlines
    overdue_deadlines = (
        db.query(func.count(Opportunity.id))
        .filter(
            Opportunity.deadline.isnot(None),
            Opportunity.deadline < today_start,
        )
        .scalar()
        or 0
    )

    # Deadlines within 3 days
    three_days = today_start + timedelta(days=3)
    deadlines_3_days = (
        db.query(func.count(Opportunity.id))
        .filter(
            Opportunity.deadline.isnot(None),
            Opportunity.deadline >= today_start,
            Opportunity.deadline < three_days,
        )
        .scalar()
        or 0
    )

    # Due follow-ups
    due_followups = (
        db.query(func.count(FollowUp.id))
        .filter(FollowUp.status == "DUE")
        .scalar()
        or 0
    )

    return {
        "overdue_actions": overdue_actions,
        "due_today_actions": due_today,
        "p0_actions": p0_actions,
        "p1_actions": p1_actions,
        "overdue_deadlines": overdue_deadlines,
        "deadlines_within_3_days": deadlines_3_days,
        "due_followups": due_followups,
    }


# ── Pipeline ──────────────────────────────────────────────────────────


def _get_pipeline(db: Session, now: datetime) -> dict:
    """Application pipeline status breakdown."""
    status_counts = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    total = sum(status_counts.values())

    active_count = sum(
        status_counts.get(s, 0) for s in _ACTIVE_APP_STATUSES
    )
    terminal_count = sum(
        status_counts.get(s, 0) for s in _TERMINAL_APP_STATUSES
    )

    # Interviews = INTERVIEW + FINAL_ROUND
    interviews = status_counts.get("INTERVIEW", 0) + status_counts.get("FINAL_ROUND", 0)
    offers = status_counts.get("OFFER", 0) + status_counts.get("ACCEPTED", 0)

    # Conversion rates (capped at 1.0)
    submitted = sum(
        status_counts.get(s, 0)
        for s in ("APPLIED", "ASSESSMENT", "INTERVIEW", "FINAL_ROUND",
                  "OFFER", "ACCEPTED", "REJECTED", "WITHDRAWN")
    )
    interview_rate = min(round(interviews / submitted, 3), 1.0) if submitted > 0 else None
    offer_rate = min(round(offers / submitted, 3), 1.0) if submitted > 0 else None

    return {
        "total": total,
        "by_status": status_counts,
        "active_count": active_count,
        "terminal_count": terminal_count,
        "interviews": interviews,
        "offers": offers,
        "interview_rate": interview_rate,
        "offer_rate": offer_rate,
    }


# ── Opportunities ─────────────────────────────────────────────────────


def _get_opportunities(db: Session, now: datetime) -> dict:
    """Opportunity metrics and match score distribution."""
    total = db.query(func.count(Opportunity.id)).scalar() or 0

    high_match = (
        db.query(func.count(Opportunity.id))
        .filter(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 80,
        )
        .scalar()
        or 0
    )

    # Match score buckets
    scored = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.match_score.isnot(None))
        .scalar()
        or 0
    )
    avg_score = db.query(func.avg(Opportunity.match_score)).scalar()

    match_distribution = {
        "90_100": (
            db.query(func.count(Opportunity.id))
            .filter(Opportunity.match_score >= 90)
            .scalar() or 0
        ),
        "80_89": (
            db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.match_score >= 80,
                Opportunity.match_score < 90,
            )
            .scalar() or 0
        ),
        "70_79": (
            db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.match_score >= 70,
                Opportunity.match_score < 80,
            )
            .scalar() or 0
        ),
        "60_69": (
            db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.match_score >= 60,
                Opportunity.match_score < 70,
            )
            .scalar() or 0
        ),
        "below_60": (
            db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.match_score.isnot(None),
                Opportunity.match_score < 60,
            )
            .scalar() or 0
        ),
        "unscored": total - scored,
    }

    # By type
    type_counts = dict(
        db.query(Opportunity.type, func.count(Opportunity.id))
        .group_by(Opportunity.type)
        .all()
    )

    # By planning horizon
    horizon_counts: dict[str, int] = {}
    opps = db.query(Opportunity.id, Opportunity.deadline).all()
    for opp_id, deadline in opps:
        hz = classify_horizon(deadline, now)
        horizon_counts[hz] = horizon_counts.get(hz, 0) + 1

    # Opportunities with/without deadlines
    with_deadline = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.deadline.isnot(None))
        .scalar()
        or 0
    )
    without_deadline = total - with_deadline

    # Opportunities not yet applied
    applied_opp_ids = db.query(Application.opportunity_id).distinct()
    not_applied = (
        db.query(func.count(Opportunity.id))
        .filter(~Opportunity.id.in_(applied_opp_ids))
        .scalar()
        or 0
    )

    return {
        "total": total,
        "high_match": high_match,
        "scored": scored,
        "average_match_score": round(float(avg_score), 1) if avg_score else None,
        "match_distribution": match_distribution,
        "by_type": type_counts,
        "by_horizon": horizon_counts,
        "with_deadline": with_deadline,
        "without_deadline": without_deadline,
        "not_applied": not_applied,
    }


# ── Summer 2027 ──────────────────────────────────────────────────────


def _get_summer_2027(db: Session, now: datetime) -> dict:
    """Summer 2027 specific metrics."""
    summer_opps = []
    opps = db.query(Opportunity).all()
    for opp in opps:
        hz = classify_horizon(opp.deadline, now)
        if hz == "SUMMER_2027":
            summer_opps.append(opp)

    total = len(summer_opps)

    high_match = sum(
        1 for o in summer_opps
        if o.match_score is not None and o.match_score >= 80
    )

    # How many have applications
    summer_opp_ids = [o.id for o in summer_opps]
    if summer_opp_ids:
        app_count = (
            db.query(func.count(Application.id))
            .filter(Application.opportunity_id.in_(summer_opp_ids))
            .scalar()
            or 0
        )
        applied_opp_ids = set(
            row[0] for row in
            db.query(Application.opportunity_id)
            .filter(Application.opportunity_id.in_(summer_opp_ids))
            .distinct()
            .all()
        )
    else:
        app_count = 0
        applied_opp_ids = set()

    not_applied = total - len(applied_opp_ids)

    # Application status breakdown for summer 2027
    summer_app_status: dict[str, int] = {}
    if summer_opp_ids:
        summer_app_status = dict(
            db.query(Application.status, func.count(Application.id))
            .filter(Application.opportunity_id.in_(summer_opp_ids))
            .group_by(Application.status)
            .all()
        )

    # Active campaigns covering summer 2027
    summer_campaigns = 0
    if summer_opp_ids:
        summer_campaigns = (
            db.query(func.count(func.distinct(CampaignOpportunity.campaign_id)))
            .join(Campaign, Campaign.id == CampaignOpportunity.campaign_id)
            .filter(
                CampaignOpportunity.opportunity_id.in_(summer_opp_ids),
                Campaign.status == "ACTIVE",
            )
            .scalar()
            or 0
        )

    return {
        "total": total,
        "high_match": high_match,
        "not_applied": not_applied,
        "applications": app_count,
        "application_status": summer_app_status,
        "active_campaigns": summer_campaigns,
    }


# ── Campaigns ─────────────────────────────────────────────────────────


def _get_campaigns(db: Session, now: datetime) -> dict:
    """Campaign status and activity."""
    status_counts = dict(
        db.query(Campaign.status, func.count(Campaign.id))
        .group_by(Campaign.status)
        .all()
    )

    total = sum(status_counts.values())
    active = status_counts.get("ACTIVE", 0)

    # Campaign opportunity counts
    total_campaign_opps = db.query(func.count(CampaignOpportunity.id)).scalar() or 0

    # Active campaign details
    active_campaigns = []
    if active > 0:
        campaigns = (
            db.query(Campaign)
            .filter(Campaign.status == "ACTIVE")
            .order_by(Campaign.created_at.desc())
            .all()
        )
        for c in campaigns:
            opp_count = (
                db.query(func.count(CampaignOpportunity.id))
                .filter(CampaignOpportunity.campaign_id == c.id)
                .scalar()
                or 0
            )
            active_campaigns.append({
                "id": c.id,
                "name": c.name,
                "type": c.type,
                "opportunity_count": opp_count,
            })

    return {
        "total": total,
        "by_status": status_counts,
        "active_count": active,
        "total_campaign_opportunities": total_campaign_opps,
        "active_campaigns": active_campaigns,
    }


# ── Outreach ──────────────────────────────────────────────────────────


def _get_outreach(db: Session) -> dict:
    """Message status breakdown."""
    status_counts = dict(
        db.query(Message.status, func.count(Message.id))
        .group_by(Message.status)
        .all()
    )

    total = sum(status_counts.values())

    approval_needed = (
        status_counts.get("PENDING_APPROVAL", 0)
        + status_counts.get("APPROVED", 0)
        + status_counts.get("READY_TO_SEND", 0)
    )

    return {
        "total": total,
        "by_status": status_counts,
        "drafts": status_counts.get("DRAFT", 0),
        "pending_approval": status_counts.get("PENDING_APPROVAL", 0),
        "approved": status_counts.get("APPROVED", 0),
        "ready_to_send": status_counts.get("READY_TO_SEND", 0),
        "sent": status_counts.get("SENT", 0),
        "approval_needed": approval_needed,
    }


# ── Follow-ups ────────────────────────────────────────────────────────


def _get_followups(db: Session, now: datetime) -> dict:
    """Follow-up status breakdown."""
    status_counts = dict(
        db.query(FollowUp.status, func.count(FollowUp.id))
        .group_by(FollowUp.status)
        .all()
    )

    total = sum(status_counts.values())

    overdue = status_counts.get("DUE", 0)
    pending = status_counts.get("PENDING", 0)
    completed = status_counts.get("COMPLETED", 0)

    return {
        "total": total,
        "by_status": status_counts,
        "overdue": overdue,
        "pending": pending,
        "completed": completed,
    }


# ── Analytics ─────────────────────────────────────────────────────────


def _get_analytics(db: Session, now: datetime) -> dict:
    """Deterministic analytics from real data."""
    # Application funnel
    app_status = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    total_opps = db.query(func.count(Opportunity.id)).scalar() or 0
    total_apps = sum(app_status.values())
    submitted = sum(
        app_status.get(s, 0)
        for s in ("APPLIED", "ASSESSMENT", "INTERVIEW", "FINAL_ROUND",
                  "OFFER", "ACCEPTED", "REJECTED", "WITHDRAWN")
    )
    interviews = app_status.get("INTERVIEW", 0) + app_status.get("FINAL_ROUND", 0)
    offers = app_status.get("OFFER", 0) + app_status.get("ACCEPTED", 0)
    accepted = app_status.get("ACCEPTED", 0)
    rejected = app_status.get("REJECTED", 0)

    # Rates (safe division, capped at 1.0)
    application_rate = min(round(total_apps / total_opps, 3), 1.0) if total_opps > 0 else None
    interview_rate = min(round(interviews / submitted, 3), 1.0) if submitted > 0 else None
    offer_rate = min(round(offers / submitted, 3), 1.0) if submitted > 0 else None
    acceptance_rate = min(round(accepted / offers, 3), 1.0) if offers > 0 else None

    # Source performance — opportunities per company
    source_perf = []
    company_opp_counts = (
        db.query(Company.name, func.count(Opportunity.id))
        .join(Opportunity, Opportunity.company_id == Company.id)
        .group_by(Company.name)
        .order_by(func.count(Opportunity.id).desc())
        .limit(10)
        .all()
    )
    for company_name, count in company_opp_counts:
        source_perf.append({"source": company_name, "opportunities": count})

    # Campaign performance
    campaign_perf = []
    active_campaigns = (
        db.query(Campaign)
        .filter(Campaign.status == "ACTIVE")
        .all()
    )
    for c in active_campaigns:
        opp_count = (
            db.query(func.count(CampaignOpportunity.id))
            .filter(CampaignOpportunity.campaign_id == c.id)
            .scalar()
            or 0
        )
        campaign_perf.append({
            "campaign": c.name,
            "opportunities": opp_count,
        })

    # Application funnel (for visualization)
    funnel = [
        {"stage": "Total Opportunities", "count": total_opps},
        {"stage": "Applications", "count": total_apps},
        {"stage": "Submitted", "count": submitted},
        {"stage": "Interviews", "count": interviews},
        {"stage": "Offers", "count": offers},
        {"stage": "Accepted", "count": accepted},
    ]

    return {
        "application_funnel": funnel,
        "application_rate": application_rate,
        "interview_rate": interview_rate,
        "offer_rate": offer_rate,
        "acceptance_rate": acceptance_rate,
        "source_performance": source_perf,
        "campaign_performance": campaign_perf,
    }


# ── Empty states ──────────────────────────────────────────────────────


def _empty_overview() -> dict:
    return {
        "total_opportunities": 0,
        "total_applications": 0,
        "open_actions": 0,
        "total_actions": 0,
        "total_campaigns": 0,
        "active_campaigns": 0,
        "high_match_opportunities": 0,
    }


def _empty_today() -> dict:
    return {
        "overdue_actions": 0,
        "due_today_actions": 0,
        "p0_actions": 0,
        "p1_actions": 0,
        "overdue_deadlines": 0,
        "deadlines_within_3_days": 0,
        "due_followups": 0,
    }


def _empty_pipeline() -> dict:
    return {
        "total": 0,
        "by_status": {},
        "active_count": 0,
        "terminal_count": 0,
        "interviews": 0,
        "offers": 0,
        "interview_rate": None,
        "offer_rate": None,
    }


def _empty_opportunities() -> dict:
    return {
        "total": 0,
        "high_match": 0,
        "scored": 0,
        "average_match_score": None,
        "match_distribution": {},
        "by_type": {},
        "by_horizon": {},
        "with_deadline": 0,
        "without_deadline": 0,
        "not_applied": 0,
    }


def _empty_summer_2027() -> dict:
    return {
        "total": 0,
        "high_match": 0,
        "not_applied": 0,
        "applications": 0,
        "application_status": {},
        "active_campaigns": 0,
    }


def _empty_campaigns() -> dict:
    return {
        "total": 0,
        "by_status": {},
        "active_count": 0,
        "total_campaign_opportunities": 0,
        "active_campaigns": [],
    }


def _empty_outreach() -> dict:
    return {
        "total": 0,
        "by_status": {},
        "drafts": 0,
        "pending_approval": 0,
        "approved": 0,
        "ready_to_send": 0,
        "sent": 0,
        "approval_needed": 0,
    }


def _empty_followups() -> dict:
    return {
        "total": 0,
        "by_status": {},
        "overdue": 0,
        "pending": 0,
        "completed": 0,
    }


def _empty_analytics() -> dict:
    return {
        "application_funnel": [],
        "application_rate": None,
        "interview_rate": None,
        "offer_rate": None,
        "acceptance_rate": None,
        "source_performance": [],
        "campaign_performance": [],
    }
