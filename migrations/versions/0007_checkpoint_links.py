"""Checkpoint crossing counts and reviewed cross-camera track links."""
from alembic import op
import sqlalchemy as sa

revision = "0007_checkpoint_links"
down_revision = "0006_vehicle_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "camera_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("x2", sa.Float(), nullable=False),
        sa.Column("y2", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
    )
    op.create_table(
        "checkpoint_crossings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("camera_checkpoints.id"), nullable=False),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("vehicle_tracks.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("vehicle_events.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("line_snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("checkpoint_id", "revision", "track_id"),
    )
    for field in ("checkpoint_id", "track_id", "event_id", "observed_at"):
        op.create_index(f"ix_checkpoint_crossings_{field}", "checkpoint_crossings", [field])
    op.create_table(
        "track_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_track_id", sa.Integer(), sa.ForeignKey("vehicle_tracks.id"), nullable=False),
        sa.Column("second_track_id", sa.Integer(), sa.ForeignKey("vehicle_tracks.id"), nullable=False),
        sa.Column("first_recognition_id", sa.Integer(), sa.ForeignKey("plate_recognitions.id"), nullable=False),
        sa.Column("second_recognition_id", sa.Integer(), sa.ForeignKey("plate_recognitions.id"), nullable=False),
        sa.Column("normalized_plate", sa.String(64), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.String(254), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("first_track_id", "second_track_id"),
    )
    for field in ("first_track_id", "second_track_id", "normalized_plate"):
        op.create_index(f"ix_track_links_{field}", "track_links", [field])


def downgrade():
    for field in ("normalized_plate", "second_track_id", "first_track_id"):
        op.drop_index(f"ix_track_links_{field}", table_name="track_links")
    op.drop_table("track_links")
    for field in ("observed_at", "event_id", "track_id", "checkpoint_id"):
        op.drop_index(f"ix_checkpoint_crossings_{field}", table_name="checkpoint_crossings")
    op.drop_table("checkpoint_crossings")
    op.drop_table("camera_checkpoints")
