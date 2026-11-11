"""Persist per-camera vehicle identities and each observed box."""
from alembic import op
import sqlalchemy as sa

revision = "0006_vehicle_tracking"
down_revision = "0005_department_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("track_key", sa.String(40), nullable=False, unique=True),
        sa.Column("camera_id", sa.String(100), nullable=False),
        sa.Column("stream_id", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_event_id", sa.Integer(), sa.ForeignKey("vehicle_events.id"), nullable=False),
        sa.Column("last_event_id", sa.Integer(), sa.ForeignKey("vehicle_events.id"), nullable=False),
        sa.Column("last_frame_number", sa.Integer()),
        sa.Column("last_bbox", sa.JSON(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
    )
    for field in ("camera_id", "stream_id", "last_seen"):
        op.create_index(f"ix_vehicle_tracks_{field}", "vehicle_tracks", [field])
    op.create_table(
        "track_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("track_id", sa.Integer(), sa.ForeignKey("vehicle_tracks.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("vehicle_events.id"), nullable=False),
        sa.Column("detection_index", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frame_number", sa.Integer()),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.UniqueConstraint("event_id", "detection_index"),
    )
    op.create_index("ix_track_observations_track_id", "track_observations", ["track_id"])
    op.create_index("ix_track_observations_event_id", "track_observations", ["event_id"])


def downgrade():
    op.drop_index("ix_track_observations_event_id", table_name="track_observations")
    op.drop_index("ix_track_observations_track_id", table_name="track_observations")
    op.drop_table("track_observations")
    for field in ("last_seen", "stream_id", "camera_id"):
        op.drop_index(f"ix_vehicle_tracks_{field}", table_name="vehicle_tracks")
    op.drop_table("vehicle_tracks")
