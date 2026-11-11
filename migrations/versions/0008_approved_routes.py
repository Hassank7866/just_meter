"""Approved route policies and movement alert reviews."""
from alembic import op
import sqlalchemy as sa

revision = "0008_approved_routes"
down_revision = "0007_checkpoint_links"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("approved_routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id")),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("camera_ids", sa.JSON(), nullable=False),
        sa.Column("camera_areas", sa.JSON(), nullable=False),
        sa.Column("corridor_polygon", sa.JSON(), nullable=False),
        sa.Column("require_assignment", sa.Boolean(), nullable=False),
        sa.Column("require_duty", sa.Boolean(), nullable=False),
        sa.Column("enforce_dates", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.String(254), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_approved_routes_department_id", "approved_routes", ["department_id"])
    op.create_index("ix_approved_routes_vehicle_id", "approved_routes", ["vehicle_id"])
    op.create_table("movement_alert_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_key", sa.String(160), nullable=False, unique=True),
        sa.Column("route_id", sa.Integer(), sa.ForeignKey("approved_routes.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewed_by", sa.String(254), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False))
    op.create_index("ix_movement_alert_reviews_route_id", "movement_alert_reviews", ["route_id"])
    op.create_index("ix_movement_alert_reviews_vehicle_id", "movement_alert_reviews", ["vehicle_id"])


def downgrade():
    op.drop_index("ix_movement_alert_reviews_vehicle_id", table_name="movement_alert_reviews")
    op.drop_index("ix_movement_alert_reviews_route_id", table_name="movement_alert_reviews")
    op.drop_table("movement_alert_reviews")
    op.drop_index("ix_approved_routes_vehicle_id", table_name="approved_routes")
    op.drop_index("ix_approved_routes_department_id", table_name="approved_routes")
    op.drop_table("approved_routes")
