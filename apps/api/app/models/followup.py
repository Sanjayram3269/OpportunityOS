from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func,Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FollowUp(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(primary_key=True)

    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )

    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
    )

    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
    )

    reason: Mapped[str | None] = mapped_column(Text)

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

Index("ix_followups_lead_id", FollowUp.lead_id)
Index("ix_followups_scheduled_for", FollowUp.scheduled_for)
Index("ix_followups_status", FollowUp.status)