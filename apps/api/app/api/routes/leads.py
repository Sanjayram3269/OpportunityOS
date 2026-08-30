from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.lead import LeadCreate, LeadRead, LeadUpdate
from app.schemas.opportunity import OpportunityRead
from app.services.lead import (
    create_lead,
    delete_lead,
    get_lead,
    list_leads,
    update_lead,
)
from app.services.opportunity import list_opportunities_by_lead

router = APIRouter(
    prefix="/leads",
    tags=["leads"],
)


@router.post(
    "",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    payload: LeadCreate,
    db: Session = Depends(get_db),
) -> LeadRead:
    return create_lead(db, payload)


@router.get(
    "",
    response_model=list[LeadRead],
)
def list_all(
    db: Session = Depends(get_db),
) -> list[LeadRead]:
    return list_leads(db)


@router.get(
    "/{lead_id}/opportunities",
    response_model=list[OpportunityRead],
)
def get_lead_opportunities(
    lead_id: int,
    db: Session = Depends(get_db),
) -> list[OpportunityRead]:
    lead = get_lead(db, lead_id)

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return list_opportunities_by_lead(db, lead_id)


@router.get(
    "/{lead_id}",
    response_model=LeadRead,
)
def get_one(
    lead_id: int,
    db: Session = Depends(get_db),
) -> LeadRead:
    lead = get_lead(db, lead_id)

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return lead


@router.patch(
    "/{lead_id}",
    response_model=LeadRead,
)
def update(
    lead_id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
) -> LeadRead:
    lead = get_lead(db, lead_id)

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return update_lead(db, lead, payload)


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    lead_id: int,
    db: Session = Depends(get_db),
) -> None:
    lead = get_lead(db, lead_id)

    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    delete_lead(db, lead)