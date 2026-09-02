"""Notification API routes — attention center.

Endpoints:
    GET  /notifications              — List notifications
    GET  /notifications/unread-count — Get unread count
    POST /notifications/{id}/read    — Mark one as read
    POST /notifications/read-all     — Mark all as read
    POST /notifications/sync         — Sync/generate notifications

Safety: No endpoint sends emails, applies to jobs, or executes external actions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.notifications import (
    get_unread_count,
    list_notifications,
    mark_all_read,
    mark_read,
    sync_notifications,
)

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
def list_notifications_route(
    unread_only: bool = Query(False, description="Filter to unread only"),
    notification_type: str | None = Query(None, description="Filter by notification type"),
    severity: str | None = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List notifications with optional filters."""
    notifications = list_notifications(
        db,
        unread_only=unread_only,
        notification_type=notification_type,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": n.id,
            "notification_type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "source_type": n.source_type,
            "source_id": n.source_id,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "dismissed_at": n.dismissed_at.isoformat() if n.dismissed_at else None,
            "due_at": n.due_at.isoformat() if n.due_at else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


@router.get("/notifications/unread-count")
def unread_count_route(db: Session = Depends(get_db)):
    """Get the count of unread notifications."""
    return {"unread_count": get_unread_count(db)}


@router.post("/notifications/{notification_id}/read")
def mark_read_route(notification_id: int, db: Session = Depends(get_db)):
    """Mark a single notification as read."""
    try:
        notification = mark_read(db, notification_id)
        db.commit()
        return {
            "id": notification.id,
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/notifications/read-all")
def mark_all_read_route(db: Session = Depends(get_db)):
    """Mark all unread notifications as read."""
    count = mark_all_read(db)
    db.commit()
    return {"marked_read": count}


@router.post("/notifications/sync")
def sync_notifications_route(db: Session = Depends(get_db)):
    """Sync/generate notifications from current system state.

    This endpoint only creates attention records.
    It does NOT send emails, does NOT apply to jobs, does NOT execute actions.
    """
    result = sync_notifications(db)
    db.commit()
    return result
