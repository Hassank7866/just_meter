"""Source coverage attestations and archived duty-review decisions."""
from alembic import op
import sqlalchemy as sa

revision = "0003_duty_verification"
down_revision = "0002_vims"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("duty_coverage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("vims_sources.id"), nullable=False, unique=True),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_age_hours", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.String(254), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("duty_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sighting_id", sa.Integer(), sa.ForeignKey("government_sightings.id"), nullable=False, unique=True),
        sa.Column("reviewed_by", sa.String(254), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False))


def downgrade():
    op.drop_table("duty_reviews")
    op.drop_table("duty_coverage")
