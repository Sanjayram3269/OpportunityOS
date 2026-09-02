"""Application timeline service — retrieves and formats application events.

Timeline events are created automatically by the application lifecycle service.
This service reads them for display.

Policy:
- No fabricated backfill for old records
- Events ordered chronologically
- Empty timeline is a valid response
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.application_event import ApplicationEvent


def get_application_timeline(
    db: Session,
    application_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get timeline events for an application, oldest first.

    Returns a list of event dicts sorted by occurred_at ascending.
    """
    events = (
        db.query(ApplicationEvent)
        .filter(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.occurred_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "label": e.label,
            "metadata": e.metadata_json,
            "occurred_at": e.occurred_at.isoformat(),
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
