"""Outreach service — draft generation and lifecycle management.

Uses the existing Message model as the persistence layer for outreach drafts.

Lifecycle:
    DRAFT → PENDING_APPROVAL → APPROVED → READY_TO_SEND
                                     ↘ REJECTED

The service:
1. Generates personalized drafts using AI (optional)
2. Persists drafts as Message records
3. Manages state transitions with validation
4. Never sends messages — that is a future channel adapter concern
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider, AIProviderError, AIPermissionError, AITimeoutError
from app.ai.providers.openai_compat import OpenAICompatProvider
from app.core.config import get_settings
from app.matching.extractor import extract_opportunity_features, extract_profile_features
from app.matching.scorer import score_match
from app.models.company import Company
from app.models.experience import Experience
from app.models.lead import Lead
from app.models.message import Message
from app.models.opportunity import Opportunity
from app.models.profile import Profile
from app.models.project import Project
from app.models.skill import Skill
from app.outreach.prompts import (
    build_lead_summary,
    build_match_result_for_outreach,
    build_opportunity_summary_for_outreach,
    build_outreach_prompt,
    build_profile_summary_for_outreach,
    SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# ── Valid lifecycle states ───────────────────────────────────────────────

DRAFT = "DRAFT"
PENDING_APPROVAL = "PENDING_APPROVAL"
APPROVED = "APPROVED"
READY_TO_SEND = "READY_TO_SEND"
REJECTED = "REJECTED"

_VALID_TRANSITIONS: dict[str, set[str]] = {
    DRAFT: {PENDING_APPROVAL, REJECTED},
    PENDING_APPROVAL: {APPROVED, REJECTED},
    APPROVED: {READY_TO_SEND, REJECTED},
    READY_TO_SEND: set(),
    REJECTED: set(),
}


class DraftStateError(Exception):
    """Raised when an invalid state transition is attempted."""


def can_transition(current: str, target: str) -> bool:
    """Check if a state transition is allowed."""
    return target in _VALID_TRANSITIONS.get(current, set())


# ── Draft generation ─────────────────────────────────────────────────────


def _get_ai_provider() -> AIProvider | None:
    """Attempt to create the AI provider from configuration."""
    try:
        settings = get_settings()
        if not settings.ai_api_key:
            return None
        return OpenAICompatProvider(
            api_url=settings.ai_api_url,
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            timeout=settings.ai_timeout,
        )
    except Exception as exc:
        logger.debug("AI provider not available for outreach: %s", exc)
        return None


def _build_draft_context(
    db: Session,
    profile: Profile,
    lead: Lead,
    opportunity: Opportunity,
) -> dict[str, Any]:
    """Build all context needed for draft generation."""
    # Load profile-related data
    skills = db.query(Skill).filter(Skill.profile_id == profile.id).all()
    projects = db.query(Project).filter(Project.profile_id == profile.id).all()
    experiences = db.query(Experience).filter(Experience.profile_id == profile.id).all()

    profile_features = extract_profile_features(
        profile, skills=skills, projects=projects, experiences=experiences,
    )

    # Opportunity features
    company = db.get(Company, opportunity.company_id)
    company_name = company.name if company else None
    opp_features = extract_opportunity_features(opportunity, company_name=company_name)

    # Match result
    match_result = score_match(profile_features, opp_features)

    # Lead company
    lead_company = None
    if lead.company_id:
        lead_co = db.get(Company, lead.company_id)
        lead_company = lead_co.name if lead_co else None

    return {
        "profile_summary": build_profile_summary_for_outreach(
            profile_name=profile.name,
            headline=profile.headline,
            skills=list(profile_features.all_skills),
            project_technologies=list(profile_features.project_technologies),
            project_descriptions=list(profile_features.project_descriptions),
            experience_titles=list(profile_features.experience_titles),
            experience_descriptions=list(profile_features.experience_descriptions),
        ),
        "lead_summary": build_lead_summary(
            lead_name=lead.name,
            lead_title=lead.title,
            lead_company=lead_company,
            lead_email=lead.email,
            lead_location=lead.location,
        ),
        "opportunity_summary": build_opportunity_summary_for_outreach(
            title=opportunity.title,
            company_name=company_name,
            description=opportunity.description,
            location=opp_features.location,
            opp_type=opportunity.type,
            source_url=opportunity.source_url,
        ),
        "match_result": build_match_result_for_outreach(
            score=match_result.score,
            matched_skills=match_result.matched_skills,
            missing_skills=match_result.missing_skills,
            explanation=match_result.explanation,
        ),
        "match_result_obj": match_result,
    }


async def generate_draft(
    db: Session,
    *,
    profile_id: int,
    lead_id: int,
    opportunity_id: int,
    channel: str = "EMAIL",
    ai_provider: AIProvider | None = None,
) -> Message:
    """Generate a personalized outreach draft.

    Args:
        db: Database session.
        profile_id: The user's profile ID.
        lead_id: The target contact's lead ID.
        opportunity_id: The opportunity ID.
        channel: Channel type (default: "EMAIL").
        ai_provider: Optional AI provider. If None, attempts auto-detection.

    Returns:
        A Message record in DRAFT status.

    Raises:
        ValueError: If profile, lead, or opportunity not found.
    """
    # Load entities
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise ValueError(f"Profile {profile_id} not found")

    lead = db.get(Lead, lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise ValueError(f"Opportunity {opportunity_id} not found")

    # Build context
    context = _build_draft_context(db, profile, lead, opportunity)

    # Generate draft
    ai_generated = False
    ai_model_used = None
    subject = None
    body = ""
    personalization_points: list[str] = []

    if ai_provider is None:
        ai_provider = _get_ai_provider()

    if ai_provider is not None:
        try:
            prompt = build_outreach_prompt(
                profile_summary=context["profile_summary"],
                lead_summary=context["lead_summary"],
                opportunity_summary=context["opportunity_summary"],
                match_result=context["match_result"],
                channel=channel,
            )

            raw_response = await ai_provider.generate_insight({
                "profile_summary": context["profile_summary"],
                "opportunity_summary": context["opportunity_summary"],
                "match_result": context["match_result"],
            })

            # The AI provider returns a dict; we parse it as outreach draft
            # For outreach, we expect: subject, body, personalization_points
            if isinstance(raw_response, dict):
                subject = raw_response.get("subject")
                body = raw_response.get("body", "")
                pp = raw_response.get("personalization_points", [])
                if isinstance(pp, list):
                    personalization_points = [str(p) for p in pp if p]
                ai_generated = True
                ai_model_used = ai_provider.model_name

        except (AIPermissionError, AITimeoutError, AIProviderError) as exc:
            logger.warning("AI draft generation failed: %s", exc)
        except Exception as exc:
            logger.error("Unexpected error in AI draft generation: %s", exc)

    # If AI didn't produce a body, create a minimal template
    if not body:
        body = _build_fallback_body(context, channel)
        if channel.upper() == "EMAIL" and not subject:
            subject = _build_fallback_subject(context)

    # Persist
    message = Message(
        lead_id=lead_id,
        opportunity_id=opportunity_id,
        channel=channel,
        direction="OUTBOUND",
        subject=subject,
        body=body,
        status=DRAFT,
        ai_generated=ai_generated,
        ai_model=ai_model_used,
        personalization_score=context["match_result_obj"].score,
    )

    # Store personalization points as metadata via prompt_version field
    # (prompt_version is the closest existing field for this)
    if personalization_points:
        message.prompt_version = json.dumps(personalization_points)

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


def _build_fallback_body(context: dict[str, Any], channel: str) -> str:
    """Build a minimal fallback body when AI is unavailable."""
    lead = context["lead_summary"]
    opp = context["opportunity_summary"]
    profile = context["profile_summary"]
    match = context["match_result"]

    lead_name = lead.get("name") or "there"
    opp_title = opp.get("title") or "the opportunity"
    company = opp.get("company") or "your team"
    profile_name = profile.get("name") or "I"
    skills = match.get("matched_skills", [])

    skills_text = ", ".join(skills[:5]) if skills else "relevant skills"

    return (
        f"Hi {lead_name},\n\n"
        f"I'm reaching out regarding the {opp_title} position at {company}. "
        f"My background in {skills_text} aligns well with this role, "
        f"and I'd love to discuss how I can contribute.\n\n"
        f"Best regards,\n{profile_name}"
    )


def _build_fallback_subject(context: dict[str, Any]) -> str:
    """Build a fallback email subject."""
    opp = context["opportunity_summary"]
    opp_title = opp.get("title") or "Opportunity"
    company = opp.get("company") or ""
    if company:
        return f"Interest in {opp_title} at {company}"
    return f"Interest in {opp_title}"


# ── Draft CRUD ───────────────────────────────────────────────────────────


def get_draft(db: Session, draft_id: int) -> Message | None:
    """Retrieve a draft by ID."""
    return db.get(Message, draft_id)


def list_drafts(
    db: Session,
    *,
    lead_id: int | None = None,
    opportunity_id: int | None = None,
    status: str | None = None,
    channel: str | None = None,
    limit: int = 50,
) -> list[Message]:
    """List drafts with optional filters."""
    stmt = select(Message)
    if lead_id is not None:
        stmt = stmt.where(Message.lead_id == lead_id)
    if opportunity_id is not None:
        stmt = stmt.where(Message.opportunity_id == opportunity_id)
    if status is not None:
        stmt = stmt.where(Message.status == status)
    if channel is not None:
        stmt = stmt.where(Message.channel == channel)
    stmt = stmt.order_by(Message.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def update_draft(
    db: Session,
    draft: Message,
    *,
    subject: str | None = None,
    body: str | None = None,
    channel: str | None = None,
) -> Message:
    """Update a draft's content. Only allowed in DRAFT or PENDING_APPROVAL state."""
    if draft.status not in (DRAFT, PENDING_APPROVAL):
        raise DraftStateError(
            f"Cannot edit draft in {draft.status} state"
        )

    if subject is not None:
        draft.subject = subject
    if body is not None:
        draft.body = body
    if channel is not None:
        draft.channel = channel

    # Reset to DRAFT if edited from PENDING_APPROVAL
    if draft.status == PENDING_APPROVAL:
        draft.status = DRAFT

    db.commit()
    db.refresh(draft)
    return draft


def transition_draft(
    db: Session,
    draft: Message,
    target_status: str,
) -> Message:
    """Transition a draft to a new status.

    Raises DraftStateError if the transition is not allowed.
    """
    if not can_transition(draft.status, target_status):
        raise DraftStateError(
            f"Cannot transition from {draft.status} to {target_status}"
        )

    draft.status = target_status
    db.commit()
    db.refresh(draft)
    return draft


def approve_draft(db: Session, draft: Message) -> Message:
    """Approve a draft (PENDING_APPROVAL → APPROVED)."""
    return transition_draft(db, draft, APPROVED)


def mark_ready(db: Session, draft: Message) -> Message:
    """Mark an APPROVED draft as ready to send (APPROVED → READY_TO_SEND)."""
    return transition_draft(db, draft, READY_TO_SEND)


def reject_draft(db: Session, draft: Message) -> Message:
    """Reject/cancel a draft."""
    return transition_draft(db, draft, REJECTED)
