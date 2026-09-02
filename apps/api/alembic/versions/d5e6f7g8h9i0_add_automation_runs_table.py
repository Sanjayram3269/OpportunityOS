"""Add automation_runs table for persistent automation run history.

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7g8h9i0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(20), nullable=False, unique=True),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_attempted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sources_succeeded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sources_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("opportunities_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("opportunities_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("opportunities_deduplicated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("opportunities_scored", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("high_match_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("summer_2027_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("now_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("upcoming_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("future_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("unknown_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("actions_generated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("notifications_generated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("followups_marked_due", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_automation_runs_started_at", "automation_runs", ["started_at"])
    op.create_index("ix_automation_runs_status", "automation_runs", ["status"])
    op.create_index("ix_automation_runs_trigger", "automation_runs", ["trigger"])


def downgrade() -> None:
    op.drop_index("ix_automation_runs_trigger", table_name="automation_runs")
    op.drop_index("ix_automation_runs_status", table_name="automation_runs")
    op.drop_index("ix_automation_runs_started_at", table_name="automation_runs")
    op.drop_table("automation_runs")
