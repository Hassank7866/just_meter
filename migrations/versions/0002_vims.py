"""VIMS sources, imported identities, assignments, duty slips and sync history."""
from alembic import op
import sqlalchemy as sa

revision = "0002_vims"
down_revision = "0001_database"
branch_labels = None
depends_on = None


def owned():
    return [sa.Column("vims_source_id", sa.Integer(), sa.ForeignKey("vims_sources.id")),
            sa.Column("vims_external_id", sa.String(100)), sa.Column("vims_payload", sa.JSON()),
            sa.UniqueConstraint("vims_source_id", "vims_external_id")]


def period():
    return [sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(30), nullable=False)]


def upgrade():
    op.create_table("vims_sources", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(100), nullable=False, unique=True),
                    sa.Column("revision", sa.Integer(), nullable=False),
                    sa.Column("exported_at", sa.DateTime(timezone=True)))
    for name in ("departments", "vehicles"):
        with op.batch_alter_table(name) as batch:
            batch.add_column(sa.Column("vims_source_id", sa.Integer()))
            batch.add_column(sa.Column("vims_external_id", sa.String(100)))
            batch.add_column(sa.Column("vims_payload", sa.JSON()))
            batch.create_foreign_key(f"fk_{name}_vims_source", "vims_sources", ["vims_source_id"], ["id"])
            batch.create_unique_constraint(f"uq_{name}_vims_identity", ["vims_source_id", "vims_external_id"])
    op.add_column("departments", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("drivers", sa.Column("id", sa.Integer(), primary_key=True), *owned(),
                    sa.Column("name", sa.String(200), nullable=False),
                    sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
                    sa.Column("active", sa.Boolean(), nullable=False))
    op.create_table("vehicle_assignments", sa.Column("id", sa.Integer(), primary_key=True), *owned(), *period(),
                    sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
                    sa.Column("driver_id", sa.Integer(), sa.ForeignKey("drivers.id"), nullable=False),
                    sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
                    sa.Column("officer_name", sa.String(200), nullable=False),
                    sa.CheckConstraint("valid_until > valid_from", name="assignment_period"))
    op.create_index("ix_vehicle_assignments_vehicle_id", "vehicle_assignments", ["vehicle_id"])
    op.create_table("duty_slips", sa.Column("id", sa.Integer(), primary_key=True), *owned(), *period(),
                    sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("vehicle_assignments.id"), nullable=False),
                    sa.Column("destination", sa.String(200), nullable=False),
                    sa.Column("purpose", sa.String(1000), nullable=False),
                    sa.Column("authorized_areas", sa.JSON(), nullable=False),
                    sa.Column("approved_by", sa.String(200), nullable=False),
                    sa.CheckConstraint("valid_until > valid_from", name="duty_period"))
    op.create_index("ix_duty_slips_assignment_id", "duty_slips", ["assignment_id"])
    op.create_table("vims_sync_runs", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("source_id", sa.Integer(), sa.ForeignKey("vims_sources.id"), nullable=False),
                    sa.Column("batch_id", sa.String(100), nullable=False),
                    sa.Column("checksum", sa.String(64), nullable=False),
                    sa.Column("exported_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("actor", sa.String(254), nullable=False),
                    sa.Column("status", sa.String(30), nullable=False),
                    sa.Column("summary", sa.JSON(), nullable=False),
                    sa.Column("changes", sa.JSON(), nullable=False),
                    sa.Column("error", sa.Text()))
    op.create_index("ix_vims_sync_runs_source_id", "vims_sync_runs", ["source_id"])
    op.create_index("ix_vims_sync_runs_batch_id", "vims_sync_runs", ["batch_id"])


def downgrade():
    for name in ("vims_sync_runs", "duty_slips", "vehicle_assignments", "drivers"):
        op.drop_table(name)
    op.drop_column("departments", "active")
    for name in ("vehicles", "departments"):
        with op.batch_alter_table(name) as batch:
            batch.drop_constraint(f"uq_{name}_vims_identity", type_="unique")
            batch.drop_constraint(f"fk_{name}_vims_source", type_="foreignkey")
            for column in ("vims_payload", "vims_external_id", "vims_source_id"):
                batch.drop_column(column)
    op.drop_table("vims_sources")
