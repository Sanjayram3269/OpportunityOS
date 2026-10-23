"""Add profile preference columns.

Revision ID: d6e7f8g9h0i1
Revises: d5e6f7g8h9i0
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d6e7f8g9h0i1"
down_revision = "d5e6f7g8h9i0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("current_city", sa.String(length=100), nullable=True))
    op.add_column("profiles", sa.Column("preferred_cities", sa.String(length=500), nullable=True))
    op.add_column("profiles", sa.Column("geographic_preference", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("degree", sa.String(length=100), nullable=True))
    op.add_column("profiles", sa.Column("field_of_study", sa.String(length=100), nullable=True))
    op.add_column("profiles", sa.Column("institution", sa.String(length=200), nullable=True))
    op.add_column("profiles", sa.Column("graduation_year", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("skills_summary", sa.String(length=1000), nullable=True))
    op.add_column("profiles", sa.Column("preferred_role_types", sa.String(length=200), nullable=True))
    op.add_column("profiles", sa.Column("minimum_compensation", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("availability_start", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("availability_end", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("work_arrangement", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("notable_achievements", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "notable_achievements")
    op.drop_column("profiles", "work_arrangement")
    op.drop_column("profiles", "availability_end")
    op.drop_column("profiles", "availability_start")
    op.drop_column("profiles", "minimum_compensation")
    op.drop_column("profiles", "preferred_role_types")
    op.drop_column("profiles", "skills_summary")
    op.drop_column("profiles", "graduation_year")
    op.drop_column("profiles", "institution")
    op.drop_column("profiles", "field_of_study")
    op.drop_column("profiles", "degree")
    op.drop_column("profiles", "geographic_preference")
    op.drop_column("profiles", "preferred_cities")
    op.drop_column("profiles", "current_city")