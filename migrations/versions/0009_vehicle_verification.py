"""Persist capture-time vehicle attribute verification and officer decisions."""
from alembic import op
import sqlalchemy as sa

revision = "0009_vehicle_verification"
down_revision = "0008_approved_routes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vehicle_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sighting_id", sa.Integer(), sa.ForeignKey("government_sightings.id"), nullable=False, unique=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id")),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False),
        sa.Column("observed", sa.JSON(), nullable=False),
        sa.Column("comparisons", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("risk_status", sa.String(40), nullable=False),
        sa.Column("reviewed_by", sa.String(254)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text(), nullable=False),
    )
    for name in ("vehicle_id", "department_id", "observed_at", "status"):
        op.create_index(f"ix_vehicle_verifications_{name}", "vehicle_verifications", [name])


def downgrade():
    op.drop_table("vehicle_verifications")
