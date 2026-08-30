from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func,Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OpportunityEvidence(Base):
    __tablename__ = "opportunity_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)

    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    evidence_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    weight: Mapped[float | None] = mapped_column(
        Float,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

Index("ix_opportunity_evidence_opportunity_id", OpportunityEvidence.opportunity_id)