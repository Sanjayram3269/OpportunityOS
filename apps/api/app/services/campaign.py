"""Campaign service — CRUD, lifecycle, membership, and summary.

Uses the existing Campaign model + new CampaignOpportunity association.
No duplicate Message or FollowUp records — campaigns organize them.

Lifecycle:
    DRAFT → ACTIVE → PAUSED → COMPLETED → ARCHIVED
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_opportunity import CampaignOpportunity
from app.models.followup import FollowUp
from app.models.message import Message
from app.models.opportunity import Opportunity

logger = logging.getLogger(__name__)

# ── Lifecycle states ─────────────────────────────────────────────────────

DRAFT = "DRAFT"
ACTIVE = "ACTIVE"
PAUSED = "PAUSED"
COMPLETED = "COMPLETED"
ARCHIVED = "ARCHIVED"

_VALID_TRANSITIONS: dict[str, set[str]] = {
    DRAFT: {ACTIVE, ARCHIVED},
    ACTIVE: {PAUSED, COMPLETED, ARCHIVED},
    PAUSED: {ACTIVE, COMPLETED, ARCHIVED},
    COMPLETED: {ARCHIVED},
    ARCHIVED: set(),
}


class CampaignStateError(Exception):
    """Raised when an invalid state transition is attempted."""


def can_transition(current: str, target: str) -> bool:
    """Check if a state transition is allowed."""
    return target in _VALID_TRANSITIONS.get(current, set())


# ── CRUD ─────────────────────────────────────────────────────────────────


def create_campaign(
    db: Session,
    *,
    name: str,
    type: str,
    description: str | None = None,
    target_description: str | None = None,
) -> Campaign:
    """Create a new campaign in DRAFT status."""
    campaign = Campaign(
        name=name,
        type=type,
        description=description,
        target_description=target_description,
        status=DRAFT,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    logger.info("Campaign created: id=%d, name=%s", campaign.id, name)
    return campaign


def get_campaign(db: Session, campaign_id: int) -> Campaign | None:
    """Retrieve a campaign by ID."""
    return db.get(Campaign, campaign_id)


def list_campaigns(
    db: Session,
    *,
    status: str | None = None,
    type: str | None = None,
    limit: int = 50,
) -> list[Campaign]:
    """List campaigns with optional filters."""
    stmt = select(Campaign)
    if status is not None:
        stmt = stmt.where(Campaign.status == status)
    if type is not None:
        stmt = stmt.where(Campaign.type == type)
    stmt = stmt.order_by(Campaign.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def update_campaign(
    db: Session,
    campaign: Campaign,
    *,
    name: str | None = None,
    type: str | None = None,
    description: str | None = None,
    target_description: str | None = None,
) -> Campaign:
    """Update campaign fields. Only allowed in DRAFT or ACTIVE state."""
    if campaign.status not in (DRAFT, ACTIVE):
        raise CampaignStateError(
            f"Cannot edit campaign in {campaign.status} state"
        )

    if name is not None:
        campaign.name = name
    if type is not None:
        campaign.type = type
    if description is not None:
        campaign.description = description
    if target_description is not None:
        campaign.target_description = target_description

    db.commit()
    db.refresh(campaign)
    return campaign


# ── State transitions ────────────────────────────────────────────────────


def transition_campaign(
    db: Session,
    campaign: Campaign,
    target_status: str,
) -> Campaign:
    """Transition a campaign to a new status."""
    if not can_transition(campaign.status, target_status):
        raise CampaignStateError(
            f"Cannot transition from {campaign.status} to {target_status}"
        )
    campaign.status = target_status
    db.commit()
    db.refresh(campaign)
    return campaign


def activate_campaign(db: Session, campaign: Campaign) -> Campaign:
    """Activate a campaign (DRAFT/PAUSED → ACTIVE)."""
    return transition_campaign(db, campaign, ACTIVE)


def pause_campaign(db: Session, campaign: Campaign) -> Campaign:
    """Pause an active campaign (ACTIVE → PAUSED)."""
    return transition_campaign(db, campaign, PAUSED)


def complete_campaign(db: Session, campaign: Campaign) -> Campaign:
    """Complete a campaign (ACTIVE/PAUSED → COMPLETED)."""
    return transition_campaign(db, campaign, COMPLETED)


def archive_campaign(db: Session, campaign: Campaign) -> Campaign:
    """Archive a campaign (any non-archived state → ARCHIVED)."""
    return transition_campaign(db, campaign, ARCHIVED)


# ── Membership ───────────────────────────────────────────────────────────


def add_opportunity_to_campaign(
    db: Session,
    campaign: Campaign,
    opportunity_id: int,
) -> CampaignOpportunity:
    """Add an opportunity to a campaign.

    Validates that the opportunity exists.
    Idempotent: if already added, returns existing record.
    """
    opp = db.get(Opportunity, opportunity_id)
    if opp is None:
        raise ValueError(f"Opportunity {opportunity_id} not found")

    # Check if already exists
    existing = db.scalar(
        select(CampaignOpportunity).where(
            CampaignOpportunity.campaign_id == campaign.id,
            CampaignOpportunity.opportunity_id == opportunity_id,
        )
    )
    if existing is not None:
        return existing

    link = CampaignOpportunity(
        campaign_id=campaign.id,
        opportunity_id=opportunity_id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    logger.info(
        "Opportunity %d added to campaign %d", opportunity_id, campaign.id
    )
    return link


def remove_opportunity_from_campaign(
    db: Session,
    campaign: Campaign,
    opportunity_id: int,
) -> bool:
    """Remove an opportunity from a campaign.

    Returns True if removed, False if not found.
    """
    link = db.scalar(
        select(CampaignOpportunity).where(
            CampaignOpportunity.campaign_id == campaign.id,
            CampaignOpportunity.opportunity_id == opportunity_id,
        )
    )
    if link is None:
        return False

    db.delete(link)
    db.commit()
    logger.info(
        "Opportunity %d removed from campaign %d", opportunity_id, campaign.id
    )
    return True


def list_campaign_opportunities(
    db: Session,
    campaign: Campaign,
) -> list[Opportunity]:
    """List all opportunities in a campaign."""
    stmt = (
        select(Opportunity)
        .join(CampaignOpportunity, CampaignOpportunity.opportunity_id == Opportunity.id)
        .where(CampaignOpportunity.campaign_id == campaign.id)
        .order_by(Opportunity.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_opportunity_campaigns(
    db: Session,
    opportunity_id: int,
) -> list[Campaign]:
    """List all campaigns containing a given opportunity."""
    stmt = (
        select(Campaign)
        .join(CampaignOpportunity, CampaignOpportunity.campaign_id == Campaign.id)
        .where(CampaignOpportunity.opportunity_id == opportunity_id)
        .order_by(Campaign.created_at.desc())
    )
    return list(db.scalars(stmt))


# ── Summary ──────────────────────────────────────────────────────────────


def get_campaign_summary(db: Session, campaign: Campaign) -> dict:
    """Build a deterministic summary of campaign activity.

    Uses actual records — no fabricated statistics.
    """
    opp_ids = list(
        db.scalars(
            select(CampaignOpportunity.opportunity_id).where(
                CampaignOpportunity.campaign_id == campaign.id
            )
        )
    )

    total_opportunities = len(opp_ids)

    # Average match score
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

    # Message counts (messages linked to opportunities in this campaign)
    drafts_count = 0
    pending_approval_count = 0
    approved_count = 0
    sent_count = 0

    if opp_ids:
        msg_status_counts = dict(
            db.query(Message.status, func.count(Message.id))
            .where(Message.opportunity_id.in_(opp_ids))
            .group_by(Message.status)
            .all()
        )
        drafts_count = msg_status_counts.get("DRAFT", 0)
        pending_approval_count = msg_status_counts.get("PENDING_APPROVAL", 0)
        approved_count = msg_status_counts.get("APPROVED", 0)
        sent_count = msg_status_counts.get("SENT", 0)

    # Follow-up counts (follow-ups linked to opportunities in this campaign)
    followups_pending = 0
    followups_completed = 0
    followups_cancelled = 0

    if opp_ids:
        fu_status_counts = dict(
            db.query(FollowUp.status, func.count(FollowUp.id))
            .where(FollowUp.opportunity_id.in_(opp_ids))
            .group_by(FollowUp.status)
            .all()
        )
        followups_pending = sum(
            fu_status_counts.get(s, 0)
            for s in ("PENDING", "DUE", "PENDING_APPROVAL", "APPROVED", "READY_TO_SEND")
        )
        followups_completed = fu_status_counts.get("COMPLETED", 0)
        followups_cancelled = fu_status_counts.get("CANCELLED", 0)

    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "total_opportunities": total_opportunities,
        "average_match_score": avg_score,
        "high_match_count": high_match_count,
        "drafts_count": drafts_count,
        "pending_approval_count": pending_approval_count,
        "approved_count": approved_count,
        "sent_count": sent_count,
        "followups_pending": followups_pending,
        "followups_completed": followups_completed,
        "followups_cancelled": followups_cancelled,
    }
