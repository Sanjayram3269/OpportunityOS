from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class CompanyBase(BaseModel):
    name: str
    domain: str | None = None
    website: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    industry: str | None = None
    company_size: str | None = None
    location: str | None = None
    description: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    website: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    industry: str | None = None
    company_size: str | None = None
    location: str | None = None
    description: str | None = None


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime