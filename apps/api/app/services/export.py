"""Export service — queries PostgreSQL and builds structured export data.

Read-only. Never modifies database records.

Uses existing planning service for horizon/priority classification.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_opportunity import CampaignOpportunity
from app.models.company import Company
from app.models.followup import FollowUp
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.opportunity_evidence import OpportunityEvidence
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.services.planning import classify_horizon, calculate_planning_priority


# ── Export options ───────────────────────────────────────────────────────


class ExportOptions:
    """Filter options for export."""

    def __init__(
        self,
        *,
        planning_horizon: str | None = None,
        min_match_score: int | None = None,
        opportunity_type: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        campaign_id: int | None = None,
        company_id: int | None = None,
        location: str | None = None,
    ):
        self.planning_horizon = planning_horizon
        self.min_match_score = min_match_score
        self.opportunity_type = opportunity_type
        self.status = status
        self.priority = priority
        self.campaign_id = campaign_id
        self.company_id = company_id
        self.location = location


# ── Sheet builders ───────────────────────────────────────────────────────


def _build_opportunities(db: Session, opts: ExportOptions) -> tuple[list[str], list[list[Any]]]:
    """Build Opportunities sheet data."""
    now = datetime.now(timezone.utc)

    stmt = select(Opportunity)
    if opts.opportunity_type:
        stmt = stmt.where(Opportunity.type == opts.opportunity_type)
    if opts.status:
        stmt = stmt.where(Opportunity.status == opts.status)
    if opts.priority:
        stmt = stmt.where(Opportunity.priority == opts.priority)
    if opts.min_match_score is not None:
        stmt = stmt.where(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= opts.min_match_score,
        )
    if opts.company_id is not None:
        stmt = stmt.where(Opportunity.company_id == opts.company_id)
    if opts.campaign_id is not None:
        stmt = stmt.join(
            CampaignOpportunity,
            CampaignOpportunity.opportunity_id == Opportunity.id,
        ).where(CampaignOpportunity.campaign_id == opts.campaign_id)

    opportunities = list(db.scalars(stmt))

    headers = [
        "ID", "Company", "Company ID", "Lead ID", "Type", "Title",
        "Description", "Source URL", "Status", "Priority",
        "Match Score", "Potential Value", "Deadline",
        "Planning Horizon", "Planning Priority",
        "Created At", "Updated At",
    ]

    rows = []
    for opp in opportunities:
        company = db.get(Company, opp.company_id)
        company_name = company.name if company else ""

        # Location filter (check company location)
        if opts.location and company:
            if opts.location.lower() not in (company.location or "").lower():
                continue

        horizon = classify_horizon(opp.deadline, now)
        if opts.planning_horizon and horizon != opts.planning_horizon:
            continue

        priority_score, _ = calculate_planning_priority(
            match_score=opp.match_score,
            deadline=opp.deadline,
            priority=opp.priority,
            status=opp.status,
            opp_type=opp.type,
            now=now,
        )

        rows.append([
            opp.id,
            company_name,
            opp.company_id,
            opp.lead_id or "",
            opp.type,
            opp.title,
            (opp.description or "")[:500],
            opp.source_url or "",
            opp.status,
            opp.priority,
            opp.match_score if opp.match_score is not None else "",
            float(opp.potential_value) if opp.potential_value is not None else "",
            opp.deadline,
            horizon,
            priority_score,
            opp.created_at,
            opp.updated_at,
        ])

    return headers, rows


def _build_companies(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build Companies sheet data."""
    companies = list(db.scalars(select(Company)))
    headers = [
        "ID", "Name", "Domain", "Website", "LinkedIn URL",
        "Industry", "Company Size", "Location", "Description",
        "Created At", "Updated At",
    ]
    rows = [
        [
            c.id, c.name, c.domain or "", c.website or "",
            c.linkedin_url or "", c.industry or "", c.company_size or "",
            c.location or "", (c.description or "")[:500],
            c.created_at, c.updated_at,
        ]
        for c in companies
    ]
    return headers, rows


def _build_leads(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build Leads sheet data."""
    leads = list(db.scalars(select(Lead)))
    headers = [
        "ID", "Company ID", "Name", "Title", "Email",
        "LinkedIn URL", "Website URL", "Location",
        "Source", "Notes", "Status",
        "Created At", "Updated At",
    ]
    rows = [
        [
            l.id, l.company_id or "", l.name, l.title or "",
            l.email or "", l.linkedin_url or "", l.website_url or "",
            l.location or "", l.source or "", (l.notes or "")[:200],
            l.status, l.created_at, l.updated_at,
        ]
        for l in leads
    ]
    return headers, rows


def _build_outreach(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build Outreach (Messages) sheet data."""
    messages = list(db.scalars(select(Message)))
    headers = [
        "ID", "Lead ID", "Opportunity ID", "Campaign ID",
        "Channel", "Direction", "Subject", "Body",
        "Status", "AI Generated", "AI Model",
        "Personalization Score", "Quality Score",
        "Sent At", "Created At",
    ]
    rows = [
        [
            m.id, m.lead_id, m.opportunity_id or "",
            m.campaign_id or "", m.channel, m.direction,
            m.subject or "", (m.body or "")[:500],
            m.status, "Yes" if m.ai_generated else "No",
            m.ai_model or "", m.personalization_score or "",
            m.quality_score or "", m.sent_at, m.created_at,
        ]
        for m in messages
    ]
    return headers, rows


def _build_followups(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build FollowUps sheet data."""
    followups = list(db.scalars(select(FollowUp)))
    headers = [
        "ID", "Lead ID", "Opportunity ID", "Message ID",
        "Scheduled For", "Status", "Reason",
        "Completed At", "Created At",
    ]
    rows = [
        [
            f.id, f.lead_id, f.opportunity_id or "",
            f.message_id or "", f.scheduled_for, f.status,
            (f.reason or "")[:300], f.completed_at, f.created_at,
        ]
        for f in followups
    ]
    return headers, rows


def _build_interactions(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build Interactions sheet data.

    Interaction has no direct opportunity_id, but can derive it
    through message_id → Message.opportunity_id.
    """
    interactions = list(db.scalars(select(Interaction)))

    # Pre-load messages for opportunity_id derivation
    msg_opp_map: dict[int, int | None] = {}
    if interactions:
        msg_ids = list({i.message_id for i in interactions if i.message_id})
        if msg_ids:
            messages = list(
                db.scalars(select(Message).where(Message.id.in_(msg_ids)))
            )
            msg_opp_map = {m.id: m.opportunity_id for m in messages}

    headers = [
        "ID", "Lead ID", "Message ID", "Opportunity ID (derived)",
        "Type", "Content", "Metadata",
        "Occurred At",
    ]
    rows = [
        [
            i.id,
            i.lead_id,
            i.message_id or "",
            msg_opp_map.get(i.message_id) or "" if i.message_id else "",
            i.type,
            (i.content or "")[:500],
            str(i.metadata_) if i.metadata_ else "",
            i.occurred_at,
        ]
        for i in interactions
    ]
    return headers, rows


def _build_evidence(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build OpportunityEvidence sheet data."""
    evidence = list(db.scalars(select(OpportunityEvidence)))
    headers = [
        "ID", "Opportunity ID", "Source", "Evidence Type",
        "Content", "Weight", "Created At",
    ]
    rows = [
        [
            e.id,
            e.opportunity_id,
            e.source,
            e.evidence_type,
            (e.content or "")[:500],
            e.weight if e.weight is not None else "",
            e.created_at,
        ]
        for e in evidence
    ]
    return headers, rows


def _build_campaigns(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build Campaigns sheet data with opportunity counts."""
    campaigns = list(db.scalars(select(Campaign)))

    # Get opportunity counts per campaign
    opp_counts = dict(
        db.query(
            CampaignOpportunity.campaign_id,
            func.count(CampaignOpportunity.opportunity_id),
        )
        .group_by(CampaignOpportunity.campaign_id)
        .all()
    )

    headers = [
        "ID", "Name", "Type", "Description", "Status",
        "Opportunities", "Created At", "Updated At",
    ]
    rows = [
        [
            c.id, c.name, c.type, (c.description or "")[:300],
            c.status, opp_counts.get(c.id, 0),
            c.created_at, c.updated_at,
        ]
        for c in campaigns
    ]
    return headers, rows


def _build_summary(db: Session) -> tuple[list[str], list[list[Any]]]:
    """Build Summary sheet with deterministic statistics."""
    now = datetime.now(timezone.utc)

    # Counts
    total_opps = db.scalar(select(func.count(Opportunity.id))) or 0
    total_companies = db.scalar(select(func.count(Company.id))) or 0
    total_leads = db.scalar(select(func.count(Lead.id))) or 0
    total_campaigns = db.scalar(select(func.count(Campaign.id))) or 0
    total_messages = db.scalar(select(func.count(Message.id))) or 0
    total_followups = db.scalar(select(func.count(FollowUp.id))) or 0

    # High match count
    high_match = db.scalar(
        select(func.count(Opportunity.id)).where(
            Opportunity.match_score.isnot(None),
            Opportunity.match_score >= 80,
        )
    ) or 0

    # By planning horizon
    all_opps = list(db.scalars(select(Opportunity)))
    horizon_counts: Counter[str] = Counter()
    for opp in all_opps:
        horizon_counts[classify_horizon(opp.deadline, now)] += 1

    # By type
    type_counts = dict(
        db.query(Opportunity.type, func.count(Opportunity.id))
        .group_by(Opportunity.type)
        .all()
    )

    # By status
    status_counts = dict(
        db.query(Opportunity.status, func.count(Opportunity.id))
        .group_by(Opportunity.status)
        .all()
    )

    # Message status counts
    msg_status = dict(
        db.query(Message.status, func.count(Message.id))
        .group_by(Message.status)
        .all()
    )

    # FollowUp status counts
    fu_status = dict(
        db.query(FollowUp.status, func.count(FollowUp.id))
        .group_by(FollowUp.status)
        .all()
    )

    # Interaction and evidence counts
    total_interactions = db.scalar(select(func.count(Interaction.id))) or 0
    total_evidence = db.scalar(select(func.count(OpportunityEvidence.id))) or 0

    # Build summary rows
    headers = ["Metric", "Value"]
    rows: list[list[Any]] = [
        ["Total Opportunities", total_opps],
        ["High Match (80+)", high_match],
        ["Total Companies", total_companies],
        ["Total Leads", total_leads],
        ["Total Campaigns", total_campaigns],
        ["Total Messages", total_messages],
        ["Total Follow-Ups", total_followups],
        ["Total Interactions", total_interactions],
        ["Total Evidence Records", total_evidence],
        ["", ""],
        ["--- Planning Horizons ---", ""],
    ]
    for hz in ("NOW", "UPCOMING", "SUMMER_2027", "FUTURE", "UNKNOWN"):
        rows.append([f"  {hz}", horizon_counts.get(hz, 0)])

    rows.append(["", ""])
    rows.append(["--- By Type ---", ""])
    for t, count in sorted(type_counts.items()):
        rows.append([f"  {t}", count])

    rows.append(["", ""])
    rows.append(["--- By Status ---", ""])
    for s, count in sorted(status_counts.items()):
        rows.append([f"  {s}", count])

    rows.append(["", ""])
    rows.append(["--- Message Status ---", ""])
    for s, count in sorted(msg_status.items()):
        rows.append([f"  {s}", count])

    rows.append(["", ""])
    rows.append(["--- Follow-Up Status ---", ""])
    for s, count in sorted(fu_status.items()):
        rows.append([f"  {s}", count])

    return headers, rows


# ── Main export function ─────────────────────────────────────────────────


def build_export_data(
    db: Session,
    options: ExportOptions | None = None,
) -> dict[str, tuple[list[str], list[list[Any]]]]:
    """Build all export data from the database.

    Returns a dict mapping sheet name to (headers, rows).
    """
    opts = options or ExportOptions()

    return {
        "opportunities": _build_opportunities(db, opts),
        "companies": _build_companies(db),
        "leads": _build_leads(db),
        "outreach": _build_outreach(db),
        "followups": _build_followups(db),
        "interactions": _build_interactions(db),
        "evidence": _build_evidence(db),
        "campaigns": _build_campaigns(db),
        "summary": _build_summary(db),
    }
