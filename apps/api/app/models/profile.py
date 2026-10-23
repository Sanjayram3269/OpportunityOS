from datetime import datetime
from sqlalchemy import DateTime, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(30))

    # Contact URLs (already present)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))

    # headline and bio (already present)
    headline: Mapped[str | None] = mapped_column(String(300))
    bio: Mapped[str | None] = mapped_column(Text)

    # ── New: Geographic preferences ──────────────────────────────────
    # User's current/city preference for opportunity targeting
    current_city: Mapped[str | None] = mapped_column(String(100))
    # Preferred cities for opportunity targeting (comma-separated in usage, stored as JSON-friendly)
    preferred_cities: Mapped[str | None] = mapped_column(String(500))
    # Geographic region preferences: "chennai", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "remote", "worldwide"
    geographic_preference: Mapped[str | None] = mapped_column(String(50))

    # ── New: Education ──────────────────────────────────────────────
    degree: Mapped[str | None] = mapped_column(String(100))
    field_of_study: Mapped[str | None] = mapped_column(String(100))
    institution: Mapped[str | None] = mapped_column(String(200))
    graduation_year: Mapped[int | None] = mapped_column(nullable=True)

    # ── New: Skills ────────────────────────────────────────────────
    # Skills are also tracked via the Skill table (many-to-many), but
    # keeping a summary field on the profile for quick access
    skills_summary: Mapped[str | None] = mapped_column(String(1000))

    # ── New: Professional preferences ───────────────────────────────
    # Preferred role families: FULL_TIME, PART_TIME, CONTRACT, FREELANCE, INTERNSHIP, RESEARCH, HACKATHON, STARTUP, VOLUNTEER, OTHER
    preferred_role_types: Mapped[str | None] = mapped_column(String(200))
    # Minimum desired compensation (annual, in INR or specified currency)
    minimum_compensation: Mapped[str | None] = mapped_column(String(50))
    # Availability window
    availability_start: Mapped[int | None] = mapped_column(nullable=True)
    availability_end: Mapped[int | None] = mapped_column(nullable=True)

    # Preferred work arrangement
    work_arrangement: Mapped[str | None] = mapped_column(String(50))

    # ── New: Achievements ──────────────────────────────────────────
    notable_achievements: Mapped[str | None] = mapped_column(Text)

    # ── Timestamps ──────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Index on email for fast lookup (already unique)
    __table_args__ = (
        Index("ix_profiles_email", "email", unique=True),
    )
