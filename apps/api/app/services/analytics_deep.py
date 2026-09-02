"""Analytics deep dive service — trends, velocity, conversion, drill-downs.

All analytics are derived from source-of-truth PostgreSQL records.
No fabricated data. Safe division-by-zero everywhere.

Sections:
- trends: applications/interviews/offers over time
- velocity: stage-to-stage duration metrics
- conversion: stage-by-stage conversion rates
- campaign_analytics: per-campaign performance
- source_analytics: per-company/source performance
- type_analytics: by opportunity type
- match_analytics: by match score bucket
- summer_2027_analytics: Summer 2027 specific
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.application_event import ApplicationEvent, EVENT_APPLICATION_SUBMITTED
from app.models.campaign import Campaign
from app.models.campaign_opportunity import CampaignOpportunity
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.planning import classify_horizon

logger = logging.getLogger(__name__)

# Match score buckets
MATCH_BUCKETS = [
    ("90_100", 90, 101),
    ("80_89", 80, 90),
    ("70_79", 70, 80),
    ("60_69", 60, 70),
    ("0_59", 0, 60),
]


def get_analytics_overview(
    db: Session,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    """Get comprehensive analytics overview with optional date filtering.

    Args:
        db: Database session
        start_date: Filter events after this date (inclusive)
        end_date: Filter events before this date (inclusive)
    """
    now = datetime.now(timezone.utc)

    # Apply defaults for date range
    if start_date is None:
        start_date = now - timedelta(days=90)
    if end_date is None:
        end_date = now

    return {
        "overview": _get_overview_stats(db),
        "trends": _get_trends(db, start_date, end_date),
        "velocity": _get_velocity(db),
        "conversion": _get_conversion(db),
        "source_analytics": _get_source_analytics(db),
        "campaign_analytics": _get_campaign_analytics(db),
        "type_analytics": _get_type_analytics(db),
        "match_analytics": _get_match_analytics(db),
        "summer_2027": _get_summer_2027_analytics(db, now),
    }


# ── Overview ──────────────────────────────────────────────────────────────


def _get_overview_stats(db: Session) -> dict:
    """Core pipeline counts."""
    total_opps = db.query(func.count(Opportunity.id)).scalar() or 0
    total_apps = db.query(func.count(Application.id)).scalar() or 0

    app_status = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    active_count = sum(
        app_status.get(s, 0)
        for s in ("NOT_APPLIED", "READY", "APPLIED", "ASSESSMENT",
                  "INTERVIEW", "FINAL_ROUND", "OFFER")
    )
    terminal_count = sum(
        app_status.get(s, 0) for s in ("ACCEPTED", "REJECTED", "WITHDRAWN")
    )
    interviews = app_status.get("INTERVIEW", 0) + app_status.get("FINAL_ROUND", 0)
    offers = app_status.get("OFFER", 0) + app_status.get("ACCEPTED", 0)

    # Safe rates
    submitted = total_apps - app_status.get("NOT_APPLIED", 0) - app_status.get("READY", 0)
    interview_rate = min(round(interviews / submitted, 3), 1.0) if submitted > 0 else None
    offer_rate = min(round(offers / submitted, 3), 1.0) if submitted > 0 else None

    return {
        "total_opportunities": total_opps,
        "total_applications": total_apps,
        "active_applications": active_count,
        "terminal_applications": terminal_count,
        "interviews": interviews,
        "offers": offers,
        "interview_rate": interview_rate,
        "offer_rate": offer_rate,
    }


# ── Trends ────────────────────────────────────────────────────────────────


def _get_trends(
    db: Session, start_date: datetime, end_date: datetime
) -> dict:
    """Applications, interviews, offers over time (daily buckets)."""
    # Get all applications with their events
    applications = db.query(Application).all()

    # Build daily counts
    daily_apps: dict[str, int] = {}
    daily_interviews: dict[str, int] = {}
    daily_offers: dict[str, int] = {}

    for app in applications:
        # Application creation
        if app.created_at:
            day = app.created_at.strftime("%Y-%m-%d")
            if start_date <= app.created_at <= end_date:
                daily_apps[day] = daily_apps.get(day, 0) + 1

        # Check events for milestones
        events = (
            db.query(ApplicationEvent)
            .filter(ApplicationEvent.application_id == app.id)
            .all()
        )
        for event in events:
            if start_date <= event.occurred_at <= end_date:
                if event.event_type == "APPLICATION_SUBMITTED":
                    day = event.occurred_at.strftime("%Y-%m-%d")
                    daily_apps[day] = daily_apps.get(day, 0) + 1
                elif event.event_type == "INTERVIEW":
                    day = event.occurred_at.strftime("%Y-%m-%d")
                    daily_interviews[day] = daily_interviews.get(day, 0) + 1
                elif event.event_type == "OFFER":
                    day = event.occurred_at.strftime("%Y-%m-%d")
                    daily_offers[day] = daily_offers.get(day, 0) + 1

    # Compute period totals
    current_total = sum(daily_apps.values())
    interview_total = sum(daily_interviews.values())
    offer_total = sum(daily_offers.values())

    # Compare with previous equivalent period
    period_days = (end_date - start_date).days
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date

    prev_apps = _count_applications_in_range(db, prev_start, prev_end)
    prev_interviews = _count_events_in_range(db, "INTERVIEW", prev_start, prev_end)
    prev_offers = _count_events_in_range(db, "OFFER", prev_start, prev_end)

    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "period_days": period_days,
        "applications": {
            "current": current_total,
            "previous": prev_apps,
            "change": current_total - prev_apps,
            "change_pct": _safe_pct(current_total, prev_apps),
        },
        "interviews": {
            "current": interview_total,
            "previous": prev_interviews,
            "change": interview_total - prev_interviews,
            "change_pct": _safe_pct(interview_total, prev_interviews),
        },
        "offers": {
            "current": offer_total,
            "previous": prev_offers,
            "change": offer_total - prev_offers,
            "change_pct": _safe_pct(offer_total, prev_offers),
        },
    }


def _count_applications_in_range(
    db: Session, start: datetime, end: datetime
) -> int:
    """Count applications created in a date range."""
    return (
        db.query(func.count(Application.id))
        .filter(Application.created_at >= start, Application.created_at <= end)
        .scalar()
        or 0
    )


def _count_events_in_range(
    db: Session, event_type: str, start: datetime, end: datetime
) -> int:
    """Count events of a type in a date range."""
    return (
        db.query(func.count(ApplicationEvent.id))
        .filter(
            ApplicationEvent.event_type == event_type,
            ApplicationEvent.occurred_at >= start,
            ApplicationEvent.occurred_at <= end,
        )
        .scalar()
        or 0
    )


def _safe_pct(current: int, previous: int) -> float | None:
    """Safe percentage change calculation."""
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


# ── Velocity ──────────────────────────────────────────────────────────────


def _get_velocity(db: Session) -> dict:
    """Calculate stage-to-stage duration metrics from real events."""
    applications = db.query(Application).all()

    transitions: dict[str, list[float]] = {}

    for app in applications:
        events = (
            db.query(ApplicationEvent)
            .filter(ApplicationEvent.application_id == app.id)
            .order_by(ApplicationEvent.occurred_at.asc())
            .all()
        )

        if len(events) < 2:
            continue

        for i in range(len(events) - 1):
            from_status = events[i].to_status
            to_status = events[i + 1].to_status
            key = f"{from_status}_to_{to_status}"
            delta = (events[i + 1].occurred_at - events[i].occurred_at).total_seconds()
            if delta > 0:
                transitions.setdefault(key, []).append(delta)

    velocity = {}
    for key, durations in transitions.items():
        days = [d / 86400 for d in durations]
        velocity[key] = {
            "count": len(days),
            "avg_days": round(statistics.mean(days), 1) if days else None,
            "median_days": round(statistics.median(days), 1) if days else None,
        }

    return {"transitions": velocity}


# ── Conversion ────────────────────────────────────────────────────────────


def _get_conversion(db: Session) -> dict:
    """Stage-by-stage conversion rates."""
    status_counts = dict(
        db.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )

    # Each stage: count at this stage or beyond
    stages = [
        "NOT_APPLIED", "READY", "APPLIED", "ASSESSMENT",
        "INTERVIEW", "FINAL_ROUND", "OFFER", "ACCEPTED",
    ]

    conversion_stages = []
    for i, stage in enumerate(stages):
        count = status_counts.get(stage, 0)
        # "at this stage or beyond" = sum of counts from this stage onward
        at_or_beyond = sum(status_counts.get(s, 0) for s in stages[i:])
        previous_beyond = sum(status_counts.get(s, 0) for s in stages[i - 1:]) if i > 0 else at_or_beyond
        rate = min(round(at_or_beyond / previous_beyond, 3), 1.0) if previous_beyond > 0 else None

        conversion_stages.append({
            "stage": stage,
            "count": count,
            "at_or_beyond": at_or_beyond,
            "conversion_rate": rate,
        })

    return {"stages": conversion_stages}


# ── Source Analytics ──────────────────────────────────────────────────────


def _get_source_analytics(db: Session) -> dict:
    """Per-company source performance."""
    companies = (
        db.query(Company.id, Company.name)
        .join(Opportunity, Opportunity.company_id == Company.id)
        .group_by(Company.id, Company.name)
        .order_by(func.count(Opportunity.id).desc())
        .limit(20)
        .all()
    )

    results = []
    for company_id, company_name in companies:
        opp_ids = [
            row[0] for row in
            db.query(Opportunity.id)
            .filter(Opportunity.company_id == company_id)
            .all()
        ]

        if not opp_ids:
            continue

        opp_count = len(opp_ids)
        high_match = (
            db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.id.in_(opp_ids),
                Opportunity.match_score.isnot(None),
                Opportunity.match_score >= 80,
            )
            .scalar()
            or 0
        )
        app_count = (
            db.query(func.count(Application.id))
            .filter(Application.opportunity_id.in_(opp_ids))
            .scalar()
            or 0
        )
        interview_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["INTERVIEW", "FINAL_ROUND"]),
            )
            .scalar()
            or 0
        )
        offer_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["OFFER", "ACCEPTED"]),
            )
            .scalar()
            or 0
        )

        results.append({
            "company": company_name,
            "opportunities": opp_count,
            "high_match": high_match,
            "applications": app_count,
            "interviews": interview_count,
            "offers": offer_count,
            "application_rate": min(round(app_count / opp_count, 3), 1.0) if opp_count > 0 else None,
            "interview_rate": min(round(interview_count / app_count, 3), 1.0) if app_count > 0 else None,
        })

    return {"sources": results}


# ── Campaign Analytics ────────────────────────────────────────────────────


def _get_campaign_analytics(db: Session) -> dict:
    """Per-campaign performance."""
    campaigns = db.query(Campaign).all()

    results = []
    for c in campaigns:
        opp_ids = [
            row[0] for row in
            db.query(CampaignOpportunity.opportunity_id)
            .filter(CampaignOpportunity.campaign_id == c.id)
            .all()
        ]

        opp_count = len(opp_ids)

        if opp_count == 0:
            results.append({
                "campaign_id": c.id,
                "campaign_name": c.name,
                "status": c.status,
                "opportunities": 0,
                "applications": 0,
                "interviews": 0,
                "offers": 0,
                "high_match": 0,
            })
            continue

        high_match = (
            db.query(func.count(Opportunity.id))
            .filter(
                Opportunity.id.in_(opp_ids),
                Opportunity.match_score.isnot(None),
                Opportunity.match_score >= 80,
            )
            .scalar()
            or 0
        )
        app_count = (
            db.query(func.count(Application.id))
            .filter(Application.opportunity_id.in_(opp_ids))
            .scalar()
            or 0
        )
        interview_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["INTERVIEW", "FINAL_ROUND"]),
            )
            .scalar()
            or 0
        )
        offer_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["OFFER", "ACCEPTED"]),
            )
            .scalar()
            or 0
        )

        results.append({
            "campaign_id": c.id,
            "campaign_name": c.name,
            "status": c.status,
            "opportunities": opp_count,
            "high_match": high_match,
            "applications": app_count,
            "interviews": interview_count,
            "offers": offer_count,
            "application_rate": min(round(app_count / opp_count, 3), 1.0) if opp_count > 0 else None,
        })

    return {"campaigns": results}


# ── Type Analytics ────────────────────────────────────────────────────────


def _get_type_analytics(db: Session) -> dict:
    """Performance by opportunity type."""
    type_counts = dict(
        db.query(Opportunity.type, func.count(Opportunity.id))
        .group_by(Opportunity.type)
        .all()
    )

    results = []
    for opp_type, count in type_counts.items():
        opp_ids = [
            row[0] for row in
            db.query(Opportunity.id)
            .filter(Opportunity.type == opp_type)
            .all()
        ]

        app_count = (
            db.query(func.count(Application.id))
            .filter(Application.opportunity_id.in_(opp_ids))
            .scalar()
            or 0
        )
        interview_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["INTERVIEW", "FINAL_ROUND"]),
            )
            .scalar()
            or 0
        )
        offer_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["OFFER", "ACCEPTED"]),
            )
            .scalar()
            or 0
        )

        results.append({
            "type": opp_type,
            "opportunities": count,
            "applications": app_count,
            "interviews": interview_count,
            "offers": offer_count,
        })

    return {"types": results}


# ── Match Analytics ───────────────────────────────────────────────────────


def _get_match_analytics(db: Session) -> dict:
    """Performance by match score bucket."""
    results = []
    for label, low, high in MATCH_BUCKETS:
        opp_ids = [
            row[0] for row in
            db.query(Opportunity.id)
            .filter(
                Opportunity.match_score.isnot(None),
                Opportunity.match_score >= low,
                Opportunity.match_score < high,
            )
            .all()
        ]

        opp_count = len(opp_ids)
        app_count = (
            db.query(func.count(Application.id))
            .filter(Application.opportunity_id.in_(opp_ids))
            .scalar()
            or 0
        )
        interview_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["INTERVIEW", "FINAL_ROUND"]),
            )
            .scalar()
            or 0
        )
        offer_count = (
            db.query(func.count(Application.id))
            .filter(
                Application.opportunity_id.in_(opp_ids),
                Application.status.in_(["OFFER", "ACCEPTED"]),
            )
            .scalar()
            or 0
        )

        results.append({
            "bucket": label,
            "range": f"{low}-{high - 1}",
            "opportunities": opp_count,
            "applications": app_count,
            "interviews": interview_count,
            "offers": offer_count,
            "application_rate": min(round(app_count / opp_count, 3), 1.0) if opp_count > 0 else None,
        })

    return {"buckets": results}


# ── Summer 2027 Analytics ─────────────────────────────────────────────────


def _get_summer_2027_analytics(db: Session, now: datetime) -> dict:
    """Summer 2027 specific analytics."""
    summer_opps = []
    opps = db.query(Opportunity).all()
    for opp in opps:
        hz = classify_horizon(opp.deadline, now)
        if hz == "SUMMER_2027":
            summer_opps.append(opp)

    total = len(summer_opps)
    if total == 0:
        return {
            "total": 0,
            "high_match": 0,
            "not_applied": 0,
            "applications": 0,
            "interviews": 0,
            "offers": 0,
            "active_campaigns": 0,
        }

    opp_ids = [o.id for o in summer_opps]

    high_match = sum(
        1 for o in summer_opps
        if o.match_score is not None and o.match_score >= 80
    )

    applied_opp_ids = set(
        row[0] for row in
        db.query(Application.opportunity_id)
        .filter(Application.opportunity_id.in_(opp_ids))
        .distinct()
        .all()
    )

    app_count = len(applied_opp_ids)
    not_applied = total - app_count

    interview_count = (
        db.query(func.count(Application.id))
        .filter(
            Application.opportunity_id.in_(opp_ids),
            Application.status.in_(["INTERVIEW", "FINAL_ROUND"]),
        )
        .scalar()
        or 0
    )
    offer_count = (
        db.query(func.count(Application.id))
        .filter(
            Application.opportunity_id.in_(opp_ids),
            Application.status.in_(["OFFER", "ACCEPTED"]),
        )
        .scalar()
        or 0
    )

    campaign_count = (
        db.query(func.count(func.distinct(CampaignOpportunity.campaign_id)))
        .join(Campaign, Campaign.id == CampaignOpportunity.campaign_id)
        .filter(
            CampaignOpportunity.opportunity_id.in_(opp_ids),
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
        "interviews": interview_count,
        "offers": offer_count,
        "active_campaigns": campaign_count,
    }


def get_campaign_drilldown(db: Session, campaign_id: int) -> dict:
    """Deep analytics for a specific campaign.

    Returns overview, conversion, activity, planning distribution,
    and application status breakdown for the campaign's opportunities.
    """
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        return {"error": "Campaign not found"}

    now = datetime.now(timezone.utc)

    # Get campaign opportunity IDs
    opp_ids = [
        row[0] for row in
        db.query(CampaignOpportunity.opportunity_id)
        .filter(CampaignOpportunity.campaign_id == campaign_id)
        .all()
    ]

    total_opps = len(opp_ids)

    if total_opps == 0:
        return {
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "campaign_status": campaign.status,
            "overview": {
                "total_opportunities": 0,
                "high_match": 0,
                "applications_started": 0,
                "applications_submitted": 0,
                "assessments": 0,
                "interviews": 0,
                "final_rounds": 0,
                "offers": 0,
                "accepted": 0,
                "rejected": 0,
                "withdrawn": 0,
            },
            "conversion": {
                "application_rate": None,
                "assessment_rate": None,
                "interview_rate": None,
                "offer_rate": None,
                "acceptance_rate": None,
            },
            "activity": {
                "open_actions": 0,
                "overdue_actions": 0,
                "outreach_pending_approval": 0,
                "outreach_ready_to_send": 0,
                "outreach_sent": 0,
                "followups_due": 0,
            },
            "planning": {
                "NOW": 0, "UPCOMING": 0, "SUMMER_2027": 0,
                "FUTURE": 0, "UNKNOWN": 0,
            },
        }

    # Overview — application status breakdown
    app_status = dict(
        db.query(Application.status, func.count(Application.id))
        .filter(Application.opportunity_id.in_(opp_ids))
        .group_by(Application.status)
        .all()
    )

    high_match = (
        db.query(func.count(Opportunity.id))
        .filter(
            Opportunity.id.in_(opp_ids),
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 80,
        )
        .scalar()
        or 0
    )

    # Count applications that have been submitted (APPLIED or beyond)
    submitted_statuses = {"APPLIED", "ASSESSMENT", "INTERVIEW", "FINAL_ROUND", "OFFER", "ACCEPTED"}
    apps_submitted = sum(app_status.get(s, 0) for s in submitted_statuses)
    apps_started = sum(app_status.get(s, 0) for s in ("READY",) + tuple(submitted_statuses))

    overview = {
        "total_opportunities": total_opps,
        "high_match": high_match,
        "applications_started": apps_started,
        "applications_submitted": apps_submitted,
        "assessments": app_status.get("ASSESSMENT", 0),
        "interviews": app_status.get("INTERVIEW", 0),
        "final_rounds": app_status.get("FINAL_ROUND", 0),
        "offers": app_status.get("OFFER", 0),
        "accepted": app_status.get("ACCEPTED", 0),
        "rejected": app_status.get("REJECTED", 0),
        "withdrawn": app_status.get("WITHDRAWN", 0),
    }

    # Conversion rates
    def safe_rate(num: int, denom: int) -> float | None:
        if denom <= 0:
            return None
        return min(round(num / denom, 3), 1.0)

    conversion = {
        "application_rate": safe_rate(apps_started, total_opps),
        "assessment_rate": safe_rate(app_status.get("ASSESSMENT", 0) + app_status.get("INTERVIEW", 0) + app_status.get("FINAL_ROUND", 0) + app_status.get("OFFER", 0) + app_status.get("ACCEPTED", 0), apps_submitted),
        "interview_rate": safe_rate(app_status.get("INTERVIEW", 0) + app_status.get("FINAL_ROUND", 0), apps_submitted),
        "offer_rate": safe_rate(app_status.get("OFFER", 0) + app_status.get("ACCEPTED", 0), apps_submitted),
        "acceptance_rate": safe_rate(app_status.get("ACCEPTED", 0), app_status.get("OFFER", 0) + app_status.get("ACCEPTED", 0)),
    }

    # Activity: actions, outreach, follow-ups
    from app.models.application import Action

    open_actions = (
        db.query(func.count(Action.id))
        .filter(
            Action.entity_type == "opportunity",
            Action.entity_id.in_(opp_ids),
            Action.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .scalar()
        or 0
    )
    overdue_actions = (
        db.query(func.count(Action.id))
        .filter(
            Action.entity_type == "opportunity",
            Action.entity_id.in_(opp_ids),
            Action.status.in_(["OPEN", "IN_PROGRESS"]),
            Action.due_at.isnot(None),
            Action.due_at < now,
        )
        .scalar()
        or 0
    )

    # Outreach for campaign opportunities
    msg_status = dict(
        db.query(Message.status, func.count(Message.id))
        .filter(Message.opportunity_id.in_(opp_ids))
        .group_by(Message.status)
        .all()
    )

    followup_due = (
        db.query(func.count(FollowUp.id))
        .filter(
            FollowUp.opportunity_id.in_(opp_ids),
            FollowUp.status.in_(["DUE", "PENDING_APPROVAL", "APPROVED", "READY_TO_SEND"]),
        )
        .scalar()
        or 0
    )

    activity = {
        "open_actions": open_actions,
        "overdue_actions": overdue_actions,
        "outreach_pending_approval": msg_status.get("PENDING_APPROVAL", 0),
        "outreach_ready_to_send": msg_status.get("READY_TO_SEND", 0),
        "outreach_sent": msg_status.get("SENT", 0),
        "followups_due": followup_due,
    }

    # Planning horizon distribution
    opps_in_campaign = [
        db.get(Opportunity, oid) for oid in opp_ids
    ]
    opps_in_campaign = [o for o in opps_in_campaign if o is not None]

    planning_dist: dict[str, int] = {}
    for opp in opps_in_campaign:
        hz = classify_horizon(opp.deadline, now)
        planning_dist[hz] = planning_dist.get(hz, 0) + 1

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "campaign_status": campaign.status,
        "overview": overview,
        "conversion": conversion,
        "activity": activity,
        "planning": {
            "NOW": planning_dist.get("NOW", 0),
            "UPCOMING": planning_dist.get("UPCOMING", 0),
            "SUMMER_2027": planning_dist.get("SUMMER_2027", 0),
            "FUTURE": planning_dist.get("FUTURE", 0),
            "UNKNOWN": planning_dist.get("UNKNOWN", 0),
        },
    }
