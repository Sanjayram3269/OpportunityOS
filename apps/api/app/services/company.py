from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.lead import Lead

from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyUpdate


def create_company(
    db: Session,
    company_data: CompanyCreate,
) -> Company:
    company = Company(
        name=company_data.name,
        domain=company_data.domain,
        website=str(company_data.website)
        if company_data.website
        else None,
        linkedin_url=str(company_data.linkedin_url)
        if company_data.linkedin_url
        else None,
        industry=company_data.industry,
        company_size=company_data.company_size,
        location=company_data.location,
        description=company_data.description,
    )

    db.add(company)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("A company with this name or domain already exists")

    db.refresh(company)

    return company


def get_company(
    db: Session,
    company_id: int,
) -> Company | None:
    statement = select(Company).where(Company.id == company_id)

    return db.scalar(statement)


def list_companies(
    db: Session,
) -> list[Company]:
    statement = select(Company).order_by(Company.id)

    return list(db.scalars(statement).all())


def update_company(
    db: Session,
    company: Company,
    company_data: CompanyUpdate,
) -> Company:
    update_data = company_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None and field in {
            "website",
            "linkedin_url",
        }:
            value = str(value)

        setattr(company, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("A company with this name or domain already exists")

    db.refresh(company)

    return company


def delete_company(
    db: Session,
    company: Company,
) -> None:
    db.delete(company)
    db.commit()

def list_company_leads(
    db: Session,
    company_id: int,
) -> list[Lead]:
    statement = (
        select(Lead)
        .where(Lead.company_id == company_id)
        .order_by(Lead.created_at.desc())
    )

    return list(db.scalars(statement).all())