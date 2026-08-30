from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OpportunityBase(BaseModel):
    company_id: int
    lead_id: int | None = None
    type: str
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    source_url: HttpUrl | None = None
    status: str = "DISCOVERED"
    priority: str = "MEDIUM"
    match_score: int | None = Field(default=None, ge=0, le=100)
    potential_value: Decimal | None = None
    deadline: datetime | None = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    company_id: int | None = None
    lead_id: int | None = None
    type: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    source_url: HttpUrl | None = None
    status: str | None = None
    priority: str | None = None
    match_score: int | None = Field(default=None, ge=0, le=100)
    potential_value: Decimal | None = None
    deadline: datetime | None = None


class OpportunityRead(OpportunityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
