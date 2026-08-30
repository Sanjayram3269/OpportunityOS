from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class LeadBase(BaseModel):
    company_id: int | None = None
    name: str
    title: str | None = None
    email: str | None = None
    linkedin_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    location: str | None = None
    source: str | None = None
    notes: str | None = None
    status: str = "DISCOVERED"


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    company_id: int | None = None
    name: str | None = None
    title: str | None = None
    email: str | None = None
    linkedin_url: HttpUrl | None = None
    website_url: HttpUrl | None = None
    location: str | None = None
    source: str | None = None
    notes: str | None = None
    status: str | None = None


class LeadRead(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime