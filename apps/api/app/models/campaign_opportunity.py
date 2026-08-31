"""Campaign ↔ Opportunity association table.

Tracks which opportunities belong to which campaigns.
A campaign can contain many opportunities; an opportunity can belong to many campaigns.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CampaignOpportunity(Base):
    __tablename__ = "campaign_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)

    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )

    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "opportunity_id", name="uq_campaign_opportunity"),
        Index("ix_campaign_opportunities_campaign_id", "campaign_id"),
        Index("ix_campaign_opportunities_opportunity_id", "opportunity_id"),
    )
