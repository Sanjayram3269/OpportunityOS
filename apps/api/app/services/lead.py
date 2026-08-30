from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadUpdate


def create_lead(db: Session, payload: LeadCreate) -> Lead:
    data = payload.model_dump()

    if data.get("linkedin_url") is not None:
        data["linkedin_url"] = str(data["linkedin_url"])

    if data.get("website_url") is not None:
        data["website_url"] = str(data["website_url"])

    lead = Lead(**data)

    db.add(lead)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(lead)
    return lead


def list_leads(db: Session) -> list[Lead]:
    statement = select(Lead).order_by(Lead.created_at.desc())
    return list(db.scalars(statement).all())


def get_lead(db: Session, lead_id: int) -> Lead | None:
    return db.get(Lead, lead_id)


def update_lead(
    db: Session,
    lead: Lead,
    payload: LeadUpdate,
) -> Lead:
    updates = payload.model_dump(exclude_unset=True)

    if updates.get("linkedin_url") is not None:
        updates["linkedin_url"] = str(updates["linkedin_url"])

    if updates.get("website_url") is not None:
        updates["website_url"] = str(updates["website_url"])

    for field, value in updates.items():
        setattr(lead, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(lead)
    return lead


def delete_lead(db: Session, lead: Lead) -> None:
    db.delete(lead)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise