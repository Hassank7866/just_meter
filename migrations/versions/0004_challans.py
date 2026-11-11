"""Persisted challan lifecycle, immutable issued document and action history."""
from alembic import op
import sqlalchemy as sa

revision = "0004_challans"
down_revision = "0003_duty_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("challans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(80), nullable=False, unique=True),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("sighting_id", sa.Integer(), sa.ForeignKey("government_sightings.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fine_amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(254), nullable=False),
        sa.Column("prepared_by", sa.String(254), nullable=False),
        sa.Column("approved_by", sa.String(254)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("issued_by", sa.String(254)),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("document", sa.LargeBinary()),
        sa.Column("document_sha256", sa.String(64)),
        sa.CheckConstraint("fine_amount >= 0", name="challan_fine_nonnegative"),
        sa.CheckConstraint("version >= 1", name="challan_version_positive"))
    op.create_index("ix_challans_vehicle_id", "challans", ["vehicle_id"])
    op.create_index("ix_challans_status", "challans", ["status"])
    op.create_table("challan_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("challan_id", sa.Integer(), sa.ForeignKey("challans.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(254), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False))
    op.create_index("ix_challan_events_challan_id", "challan_events", ["challan_id"])


def downgrade():
    op.drop_table("challan_events")
    op.drop_table("challans")
