from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.company import CompanyCreate, CompanyRead, CompanyUpdate
from app.schemas.lead import LeadRead
from app.schemas.opportunity import OpportunityRead
from app.services.company import (
    create_company,
    delete_company,
    get_company,
    list_company_leads,
    list_companies,
    update_company,
)
from app.services.opportunity import list_opportunities_by_company


router = APIRouter(
    prefix="/companies",
    tags=["companies"],
)


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    company_data: CompanyCreate,
    db: Session = Depends(get_db),
) -> CompanyRead:
    try:
        return create_company(db, company_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[CompanyRead],
)
def list_all(
    db: Session = Depends(get_db),
) -> list[CompanyRead]:
    return list_companies(db)


@router.get(
    "/{company_id}/leads",
    response_model=list[LeadRead],
)
def get_company_leads(
    company_id: int,
    db: Session = Depends(get_db),
) -> list[LeadRead]:
    company = get_company(db, company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return list_company_leads(db, company_id)


@router.get(
    "/{company_id}/opportunities",
    response_model=list[OpportunityRead],
)
def get_company_opportunities(
    company_id: int,
    db: Session = Depends(get_db),
) -> list[OpportunityRead]:
    company = get_company(db, company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return list_opportunities_by_company(db, company_id)


@router.get(
    "/{company_id}",
    response_model=CompanyRead,
)
def get_one(
    company_id: int,
    db: Session = Depends(get_db),
) -> CompanyRead:
    company = get_company(db, company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return company


@router.patch(
    "/{company_id}",
    response_model=CompanyRead,
)
def update(
    company_id: int,
    company_data: CompanyUpdate,
    db: Session = Depends(get_db),
) -> CompanyRead:
    company = get_company(db, company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    try:
        return update_company(db, company, company_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    company_id: int,
    db: Session = Depends(get_db),
) -> None:
    company = get_company(db, company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    delete_company(db, company)