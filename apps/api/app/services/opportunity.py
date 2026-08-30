from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.opportunity import Opportunity
from app.schemas.opportunity import OpportunityCreate, OpportunityUpdate


def create_opportunity(
    db: Session,
    payload: OpportunityCreate,
) -> Opportunity:
    data = payload.model_dump()

    if data.get("source_url") is not None:
        data["source_url"] = str(data["source_url"])

    opportunity = Opportunity(**data)

    db.add(opportunity)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(opportunity)
    return opportunity


def get_opportunity(
    db: Session,
    opportunity_id: int,
) -> Opportunity | None:
    return db.get(Opportunity, opportunity_id)


def list_opportunities(db: Session) -> list[Opportunity]:
    statement = select(Opportunity).order_by(Opportunity.created_at.desc())
    return list(db.scalars(statement).all())


def update_opportunity(
    db: Session,
    opportunity: Opportunity,
    payload: OpportunityUpdate,
) -> Opportunity:
    updates = payload.model_dump(exclude_unset=True)

    if updates.get("source_url") is not None:
        updates["source_url"] = str(updates["source_url"])

    for field, value in updates.items():
        setattr(opportunity, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise

    db.refresh(opportunity)
    return opportunity


def delete_opportunity(db: Session, opportunity: Opportunity) -> None:
    db.delete(opportunity)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


def list_opportunities_by_company(
    db: Session,
    company_id: int,
) -> list[Opportunity]:
    statement = (
        select(Opportunity)
        .where(Opportunity.company_id == company_id)
        .order_by(Opportunity.created_at.desc())
    )
    return list(db.scalars(statement).all())


def list_opportunities_by_lead(
    db: Session,
    lead_id: int,
) -> list[Opportunity]:
    statement = (
        select(Opportunity)
        .where(Opportunity.lead_id == lead_id)
        .order_by(Opportunity.created_at.desc())
    )
    return list(db.scalars(statement).all())
