"""Pydantic schemas for the Follow-up Engine API."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Request schemas ──────────────────────────────────────────────────────


class FollowUpCreateRequest(BaseModel):
    """Request to create a new follow-up."""

    lead_id: int
    opportunity_id: int | None = Field(
        default=None,
        description="Related opportunity (optional)",
    )
    message_id: int | None = Field(
        default=None,
        description="Related message/interaction (optional)",
    )
    scheduled_for: datetime = Field(
        description="When the follow-up should become due (must be timezone-aware)",
    )
    reason: str | None = Field(
        default=None,
        description="Why this follow-up is needed",
    )

    @field_validator("scheduled_for")
    @classmethod
    def reject_naive_datetime(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "scheduled_for must be timezone-aware. "
                "Use a timezone-aware datetime (e.g. 2026-01-01T12:00:00+00:00)."
            )
        return v


class FollowUpUpdateRequest(BaseModel):
    """Request to update a follow-up's content."""

    scheduled_for: datetime | None = Field(
        default=None,
        description="Updated due time (must be timezone-aware)",
    )
    reason: str | None = Field(
        default=None,
        description="Updated reason/notes",
    )

    @field_validator("scheduled_for")
    @classmethod
    def reject_naive_datetime(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError(
                "scheduled_for must be timezone-aware. "
                "Use a timezone-aware datetime (e.g. 2026-01-01T12:00:00+00:00)."
            )
        return v


# ── Response schemas ─────────────────────────────────────────────────────


class FollowUpResponse(BaseModel):
    """Response for a single follow-up."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    opportunity_id: int | None = None
    message_id: int | None = None
    scheduled_for: datetime
    status: str
    reason: str | None = None
    completed_at: datetime | None = None
    created_at: datetime


class FollowUpListResponse(BaseModel):
    """Response for listing follow-ups."""

    total: int
    follow_ups: list[FollowUpResponse]


class FollowUpStateTransitionResponse(BaseModel):
    """Response after a state transition."""

    id: int
    previous_status: str
    new_status: str
    message: str
