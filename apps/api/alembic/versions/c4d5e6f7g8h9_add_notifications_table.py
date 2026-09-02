"""Add notifications table for attention system.

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "c4d5e6f7g8h9"
down_revision = "b3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notifications_notification_type",
        "notifications",
        ["notification_type"],
    )
    op.create_index(
        "ix_notifications_source",
        "notifications",
        ["source_type", "source_id"],
    )
    op.create_index(
        "ix_notifications_read_at",
        "notifications",
        ["read_at"],
    )
    op.create_index(
        "ix_notifications_severity",
        "notifications",
        ["severity"],
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", "notifications")
    op.drop_index("ix_notifications_severity", "notifications")
    op.drop_index("ix_notifications_read_at", "notifications")
    op.drop_index("ix_notifications_source", "notifications")
    op.drop_index("ix_notifications_notification_type", "notifications")
    op.drop_table("notifications")
