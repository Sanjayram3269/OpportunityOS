"""Follow-up API routes — CRUD + state management.

Endpoints:
    POST   /follow-ups                  → Create a follow-up
    GET    /follow-ups                  → List follow-ups
    GET    /follow-ups/{id}             → Get a follow-up
    PATCH  /follow-ups/{id}             → Update a follow-up
    POST   /follow-ups/{id}/mark-due    → Mark as due (if scheduled_for passed)
    POST   /follow-ups/{id}/submit      → Submit for approval
    POST   /follow-ups/{id}/approve     → Approve
    POST   /follow-ups/{id}/ready       → Mark as ready to send
    POST   /follow-ups/{id}/complete    → Mark as completed
    POST   /follow-ups/{id}/cancel      → Cancel

No emails are sent from these endpoints.
Actual delivery goes through the existing outreach/send workflow.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.followup import (
    FollowUpCreateRequest,
    FollowUpListResponse,
    FollowUpResponse,
    FollowUpStateTransitionResponse,
    FollowUpUpdateRequest,
)
from app.services.followup import (
    APPROVED,
    CANCELLED,
    COMPLETED,
    DUE,
    PENDING,
    PENDING_APPROVAL,
    READY_TO_SEND,
    FollowUpStateError,
    approve_followup,
    cancel_followup,
    complete_followup,
    create_followup,
    get_followup,
    list_followups,
    mark_due,
    mark_followup_ready,
    submit_followup,
    update_followup,
)

router = APIRouter(
    prefix="/follow-ups",
    tags=["follow-ups"],
)


@router.post(
    "",
    response_model=FollowUpResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a follow-up",
    description=(
        "Create a new follow-up action tied to a lead. "
        "Optionally linked to an opportunity and/or message. "
        "Starts in PENDING status."
    ),
)
def create_new_followup(
    request: FollowUpCreateRequest,
    db: Session = Depends(get_db),
) -> FollowUpResponse:
    try:
        followup = create_followup(
            db,
            lead_id=request.lead_id,
            opportunity_id=request.opportunity_id,
            message_id=request.message_id,
            scheduled_for=request.scheduled_for,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    return FollowUpResponse.model_validate(followup)


@router.get(
    "",
    response_model=FollowUpListResponse,
    summary="List follow-ups",
    description="List follow-ups with optional filters for lead, opportunity, or status.",
)
def list_all_followups(
    lead_id: int | None = Query(default=None),
    opportunity_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> FollowUpListResponse:
    followups = list_followups(
        db,
        lead_id=lead_id,
        opportunity_id=opportunity_id,
        status=status_filter,
        limit=limit,
    )
    return FollowUpListResponse(
        total=len(followups),
        follow_ups=[FollowUpResponse.model_validate(f) for f in followups],
    )


@router.get(
    "/{followup_id}",
    response_model=FollowUpResponse,
    summary="Get a specific follow-up",
)
def get_single_followup(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )
    return FollowUpResponse.model_validate(followup)


@router.patch(
    "/{followup_id}",
    response_model=FollowUpResponse,
    summary="Update a follow-up",
    description=(
        "Update scheduled_for or reason. "
        "Only allowed in PENDING or DUE status."
    ),
)
def update_single_followup(
    followup_id: int,
    request: FollowUpUpdateRequest,
    db: Session = Depends(get_db),
) -> FollowUpResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    try:
        updated = update_followup(
            db,
            followup,
            scheduled_for=request.scheduled_for,
            reason=request.reason,
        )
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpResponse.model_validate(updated)


@router.post(
    "/{followup_id}/mark-due",
    response_model=FollowUpStateTransitionResponse,
    summary="Mark a follow-up as due",
    description=(
        "Check if a PENDING follow-up's scheduled_for has passed and mark it DUE. "
        "Does not send anything."
    ),
)
def mark_followup_due(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpStateTransitionResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    previous = followup.status
    try:
        updated = mark_due(db, followup)
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Follow-up marked as due",
    )


@router.post(
    "/{followup_id}/submit",
    response_model=FollowUpStateTransitionResponse,
    summary="Submit follow-up for approval",
    description="Transition a DUE follow-up to PENDING_APPROVAL.",
)
def submit_single_followup(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpStateTransitionResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    previous = followup.status
    try:
        updated = submit_followup(db, followup)
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Follow-up submitted for approval",
    )


@router.post(
    "/{followup_id}/approve",
    response_model=FollowUpStateTransitionResponse,
    summary="Approve a follow-up",
    description="Approve a PENDING_APPROVAL follow-up.",
)
def approve_single_followup(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpStateTransitionResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    previous = followup.status
    try:
        updated = approve_followup(db, followup)
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Follow-up approved",
    )


@router.post(
    "/{followup_id}/ready",
    response_model=FollowUpStateTransitionResponse,
    summary="Mark follow-up as ready to send",
    description=(
        "Mark an APPROVED follow-up as READY_TO_SEND. "
        "No messages are sent — this is a workflow state change only."
    ),
)
def mark_followup_ready_endpoint(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpStateTransitionResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    previous = followup.status
    try:
        updated = mark_followup_ready(db, followup)
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Follow-up marked as ready to send",
    )


@router.post(
    "/{followup_id}/complete",
    response_model=FollowUpStateTransitionResponse,
    summary="Mark follow-up as completed",
    description="Mark a READY_TO_SEND follow-up as COMPLETED.",
)
def complete_single_followup(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpStateTransitionResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    previous = followup.status
    try:
        updated = complete_followup(db, followup)
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Follow-up completed",
    )


@router.post(
    "/{followup_id}/cancel",
    response_model=FollowUpStateTransitionResponse,
    summary="Cancel a follow-up",
    description="Cancel a follow-up from any non-terminal state.",
)
def cancel_single_followup(
    followup_id: int,
    db: Session = Depends(get_db),
) -> FollowUpStateTransitionResponse:
    followup = get_followup(db, followup_id)
    if followup is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up not found",
        )

    previous = followup.status
    try:
        updated = cancel_followup(db, followup)
    except FollowUpStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return FollowUpStateTransitionResponse(
        id=updated.id,
        previous_status=previous,
        new_status=updated.status,
        message="Follow-up cancelled",
    )
