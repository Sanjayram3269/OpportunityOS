"""add_applications_and_actions_tables

Revision ID: a1b2c3d4e5f6
Revises: 4566393fef95
Create Date: 2026-09-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "4566393fef95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "opportunity_id",
            sa.Integer(),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="NOT_APPLIED"),
        sa.Column("application_url", sa.String(1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_change_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_applications_opportunity_id", "applications", ["opportunity_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_lead_id", "applications", ["lead_id"])

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="P3"),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_actions_action_type", "actions", ["action_type"])
    op.create_index("ix_actions_status", "actions", ["status"])
    op.create_index("ix_actions_priority", "actions", ["priority"])
    op.create_index("ix_actions_entity_type_id", "actions", ["entity_type", "entity_id"])
    op.create_index("ix_actions_due_at", "actions", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_actions_due_at", "actions")
    op.drop_index("ix_actions_entity_type_id", "actions")
    op.drop_index("ix_actions_priority", "actions")
    op.drop_index("ix_actions_status", "actions")
    op.drop_index("ix_actions_action_type", "actions")
    op.drop_table("actions")

    op.drop_index("ix_applications_lead_id", "applications")
    op.drop_index("ix_applications_status", "applications")
    op.drop_index("ix_applications_opportunity_id", "applications")
    op.drop_table("applications")
