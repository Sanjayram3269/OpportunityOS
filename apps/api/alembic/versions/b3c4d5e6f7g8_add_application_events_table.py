"""Add application_events table for timeline tracking.

Revision ID: b3c4d5e6f7g8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "b3c4d5e6f7g8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_application_events_application_id",
        "application_events",
        ["application_id"],
    )
    op.create_index(
        "ix_application_events_event_type",
        "application_events",
        ["event_type"],
    )
    op.create_index(
        "ix_application_events_occurred_at",
        "application_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_application_events_app_occurred",
        "application_events",
        ["application_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_application_events_app_occurred", "application_events")
    op.drop_index("ix_application_events_occurred_at", "application_events")
    op.drop_index("ix_application_events_event_type", "application_events")
    op.drop_index("ix_application_events_application_id", "application_events")
    op.drop_table("application_events")
