from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityRead,
    OpportunityUpdate,
)
from app.services.opportunity import (
    create_opportunity,
    delete_opportunity,
    get_opportunity,
    list_opportunities,
    update_opportunity,
)

router = APIRouter(
    prefix="/opportunities",
    tags=["opportunities"],
)


@router.post(
    "",
    response_model=OpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
) -> OpportunityRead:
    return create_opportunity(db, payload)


@router.get(
    "",
    response_model=list[OpportunityRead],
)
def list_all(
    db: Session = Depends(get_db),
) -> list[OpportunityRead]:
    return list_opportunities(db)


@router.get(
    "/{opportunity_id}",
    response_model=OpportunityRead,
)
def get_one(
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> OpportunityRead:
    opportunity = get_opportunity(db, opportunity_id)

    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    return opportunity


@router.patch(
    "/{opportunity_id}",
    response_model=OpportunityRead,
)
def update(
    opportunity_id: int,
    payload: OpportunityUpdate,
    db: Session = Depends(get_db),
) -> OpportunityRead:
    opportunity = get_opportunity(db, opportunity_id)

    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    return update_opportunity(db, opportunity, payload)


@router.delete(
    "/{opportunity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    opportunity_id: int,
    db: Session = Depends(get_db),
) -> None:
    opportunity = get_opportunity(db, opportunity_id)

    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    delete_opportunity(db, opportunity)
