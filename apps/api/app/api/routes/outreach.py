"""Outreach Draft API routes — channel-agnostic draft generation + approval workflow.

Endpoints:
    POST   /outreach/drafts              → Generate a new draft
    GET    /outreach/drafts              → List drafts
    GET    /outreach/drafts/{id}         → Get a draft
    PATCH  /outreach/drafts/{id}         → Update a draft
    POST   /outreach/drafts/{id}/submit  → Submit for approval
    POST   /outreach/drafts/{id}/approve → Approve a draft
    POST   /outreach/drafts/{id}/ready   → Mark as ready to send
    POST   /outreach/drafts/{id}/reject  → Reject/cancel a draft

No messages are ever sent. The workflow ends at READY_TO_SEND.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.outreach import (
    DraftCreateRequest,
    DraftListResponse,
    DraftResponse,
    DraftStateTransitionResponse,
    DraftUpdateRequest,
)
from app.services.outreach import (
    APPROVED,
    DRAFT,
    PENDING_APPROVAL,
    REJECTED,
    READY_TO_SEND,
    DraftStateError,
    approve_draft,
    generate_draft,
    get_draft,
    list_drafts,
    mark_ready,
    reject_draft,
    transition_draft,
    update_draft,
)

router = APIRouter(
    prefix="/outreach",
    tags=["outreach"],
)


@router.post(
    "/drafts",
    response_model=DraftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new outreach draft",
    description=(
        "Generate a personalized outreach draft for a lead about an opportunity. "
        "Uses AI when available, falls back to a template otherwise. "
        "The draft starts in DRAFT status and must be explicitly approved."
    ),
)
async def create_draft(
    request: DraftCreateRequest,
    db: Session = Depends(get_db),
) -> DraftResponse:
    try:
        message = await generate_draft(
            db,
            profile_id=request.profile_id,
            lead_id=request.lead_id,
            opportunity_id=request.opportunity_id,
            channel=request.channel,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return DraftResponse.from_message(message)


@router.get(
    "/drafts",
    response_model=DraftListResponse,
    summary="List outreach drafts",
    description="List drafts with optional filters for lead, opportunity, status, or channel.",
)
def list_all_drafts(
    lead_id: int | None = Query(default=None),
    opportunity_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DraftListResponse:
    drafts = list_drafts(
        db,
        lead_id=lead_id,
        opportunity_id=opportunity_id,
        status=status_filter,
        channel=channel,
        limit=limit,
    )
    return DraftListResponse(
        total=len(drafts),
        drafts=[DraftResponse.from_message(d) for d in drafts],
    )


@router.get(
    "/drafts/{draft_id}",
    response_model=DraftResponse,
    summary="Get a specific draft",
)
def get_single_draft(
    draft_id: int,
    db: Session = Depends(get_db),
) -> DraftResponse:
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )
    return DraftResponse.from_message(draft)


@router.patch(
    "/drafts/{draft_id}",
    response_model=DraftResponse,
    summary="Update a draft's content",
    description=(
        "Update the subject, body, or channel of a draft. "
        "Only allowed in DRAFT or PENDING_APPROVAL status. "
        "Editing a PENDING_APPROVAL draft resets it to DRAFT."
    ),
)
def update_single_draft(
    draft_id: int,
    request: DraftUpdateRequest,
    db: Session = Depends(get_db),
) -> DraftResponse:
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    try:
        updated = update_draft(
            db,
            draft,
            subject=request.subject,
            body=request.body,
            channel=request.channel,
        )
    except DraftStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return DraftResponse.from_message(updated)


@router.post(
    "/drafts/{draft_id}/submit",
    response_model=DraftStateTransitionResponse,
    summary="Submit draft for approval",
    description="Transition a DRAFT to PENDING_APPROVAL status.",
)
def submit_draft(
    draft_id: int,
    db: Session = Depends(get_db),
) -> DraftStateTransitionResponse:
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    previous = draft.status
    try:
        updated = transition_draft(db, draft, PENDING_APPROVAL)
    except DraftStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return DraftStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Draft submitted for approval",
    )


@router.post(
    "/drafts/{draft_id}/approve",
    response_model=DraftStateTransitionResponse,
    summary="Approve a draft",
    description=(
        "Approve a PENDING_APPROVAL draft. "
        "The draft transitions to APPROVED, then can be moved to READY_TO_SEND."
    ),
)
def approve_single_draft(
    draft_id: int,
    db: Session = Depends(get_db),
) -> DraftStateTransitionResponse:
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    previous = draft.status
    try:
        updated = approve_draft(db, draft)
    except DraftStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return DraftStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Draft approved",
    )


@router.post(
    "/drafts/{draft_id}/ready",
    response_model=DraftStateTransitionResponse,
    summary="Mark draft as ready to send",
    description=(
        "Mark an APPROVED draft as READY_TO_SEND. "
        "Only APPROVED drafts can be marked ready. "
        "No messages are sent — this is a workflow state change only."
    ),
)
def mark_draft_ready(
    draft_id: int,
    db: Session = Depends(get_db),
) -> DraftStateTransitionResponse:
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    previous = draft.status
    try:
        updated = mark_ready(db, draft)
    except DraftStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return DraftStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Draft marked as ready to send",
    )


@router.post(
    "/drafts/{draft_id}/reject",
    response_model=DraftStateTransitionResponse,
    summary="Reject or cancel a draft",
    description="Reject or cancel a draft from DRAFT, PENDING_APPROVAL, or APPROVED status.",
)
def reject_single_draft(
    draft_id: int,
    db: Session = Depends(get_db),
) -> DraftStateTransitionResponse:
    draft = get_draft(db, draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    previous = draft.status
    try:
        updated = reject_draft(db, draft)
    except DraftStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return DraftStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Draft rejected",
    )
