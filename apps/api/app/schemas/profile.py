from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, HttpUrl


class ProfileBase(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    headline: str | None = None
    bio: str | None = None


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    headline: str | None = None
    bio: str | None = None


class ProfileRead(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime