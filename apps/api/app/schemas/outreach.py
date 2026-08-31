"""Pydantic schemas for the Outreach Draft API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ──────────────────────────────────────────────────────


class DraftCreateRequest(BaseModel):
    """Request to generate a new outreach draft."""

    profile_id: int
    lead_id: int
    opportunity_id: int
    channel: str = Field(
        default="EMAIL",
        description="Channel type (EMAIL, LINKEDIN, etc.)",
    )


class DraftUpdateRequest(BaseModel):
    """Request to update a draft's content."""

    subject: str | None = Field(
        default=None,
        max_length=500,
        description="Updated subject (EMAIL channel)",
    )
    body: str | None = Field(
        default=None,
        description="Updated message body",
    )
    channel: str | None = Field(
        default=None,
        description="Updated channel type",
    )


# ── Response schemas ─────────────────────────────────────────────────────


class DraftResponse(BaseModel):
    """Response for a single outreach draft."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    opportunity_id: int | None = None
    channel: str
    direction: str
    subject: str | None = None
    body: str
    status: str
    ai_generated: bool
    ai_model: str | None = None
    personalization_score: int | None = None
    personalization_points: list[str] = Field(default_factory=list)
    created_at: datetime

    @classmethod
    def from_message(cls, message: Message) -> DraftResponse:
        """Create a DraftResponse from a Message ORM object."""
        # Parse personalization_points from prompt_version JSON
        pp: list[str] = []
        if message.prompt_version:
            try:
                parsed = json.loads(message.prompt_version)
                if isinstance(parsed, list):
                    pp = [str(p) for p in parsed if p]
            except (json.JSONDecodeError, TypeError):
                pass

        return cls(
            id=message.id,
            lead_id=message.lead_id,
            opportunity_id=message.opportunity_id,
            channel=message.channel,
            direction=message.direction,
            subject=message.subject,
            body=message.body,
            status=message.status,
            ai_generated=message.ai_generated,
            ai_model=message.ai_model,
            personalization_score=message.personalization_score,
            personalization_points=pp,
            created_at=message.created_at,
        )


class DraftListResponse(BaseModel):
    """Response for listing drafts."""

    total: int
    drafts: list[DraftResponse]


class DraftStateTransitionResponse(BaseModel):
    """Response after a state transition."""

    id: int
    previous_status: str
    new_status: str
    message: str


# Need to import json for from_message
import json  # noqa: E402
from app.models.message import Message  # noqa: E402
