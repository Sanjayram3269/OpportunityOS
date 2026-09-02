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
