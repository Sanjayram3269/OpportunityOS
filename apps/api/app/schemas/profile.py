from datetime import datetime
from pydantic import BaseModel, EmailStr, HttpUrl


class ProfileBase(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None
    headline: str | None = None
    bio: str | None = None

    # ── New: Geographic preferences ──────────────────────────────────
    current_city: str | None = None
    preferred_cities: str | None = None
    geographic_preference: str | None = None

    # ── New: Education ──────────────────────────────────────────────
    degree: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    graduation_year: int | None = None

    # ── New: Skills ────────────────────────────────────────────────
    skills_summary: str | None = None

    # ── New: Professional preferences ───────────────────────────────
    preferred_role_types: str | None = None
    minimum_compensation: str | None = None
    availability_start: int | None = None
    availability_end: int | None = None
    work_arrangement: str | None = None

    # ── New: Achievements ──────────────────────────────────────────
    notable_achievements: str | None = None


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

    # ── New: Geographic preferences ──────────────────────────────────
    current_city: str | None = None
    preferred_cities: str | None = None
    geographic_preference: str | None = None

    # ── New: Education ──────────────────────────────────────────────
    degree: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    graduation_year: int | None = None

    # ── New: Skills ────────────────────────────────────────────────
    skills_summary: str | None = None

    # ── New: Professional preferences ───────────────────────────────
    preferred_role_types: str | None = None
    minimum_compensation: str | None = None
    availability_start: int | None = None
    availability_end: int | None = None
    work_arrangement: str | None = None

    # ── New: Achievements ──────────────────────────────────────────
    notable_achievements: str | None = None


class ProfileRead(ProfileBase):
    model_config = dict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    # ── New fields ────────────────────────────────────────────────
    current_city: str | None = None
    preferred_cities: str | None = None
    geographic_preference: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    graduation_year: int | None = None
    skills_summary: str | None = None
    preferred_role_types: str | None = None
    minimum_compensation: str | None = None
    availability_start: int | None = None
    availability_end: int | None = None
    work_arrangement: str | None = None
    notable_achievements: str | None = None
