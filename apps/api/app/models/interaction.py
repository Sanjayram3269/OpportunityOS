from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text,Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True)

    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
    )

    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    content: Mapped[str | None] = mapped_column(Text)

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

Index("ix_interactions_lead_id", Interaction.lead_id)
Index("ix_interactions_message_id", Interaction.message_id)
Index("ix_interactions_occurred_at", Interaction.occurred_at)