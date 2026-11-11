"""Department access, revocable sessions and capture-time record ownership."""
from alembic import op
import sqlalchemy as sa

revision = "0005_department_access"
down_revision = "0004_challans"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("users", "government_sightings", "evidence", "audit_events", "challans"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(f"fk_{table}_department", "departments", ["department_id"], ["id"])
            if table != "users":
                batch.create_index(f"ix_{table}_department_id", ["department_id"])
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    bind = op.get_bind()
    metadata = sa.MetaData()
    departments = sa.Table("departments", metadata, autoload_with=bind)
    names = dict(bind.execute(sa.select(departments.c.name, departments.c.id)).all())
    # Historical ownership comes from capture snapshots, never today's vehicle owner.
    for name in ("government_sightings", "evidence", "challans"):
        table = sa.Table(name, metadata, autoload_with=bind)
        payload = table.c.snapshot if name == "challans" else table.c.payload
        for identifier, record in bind.execute(sa.select(table.c.id, payload)).all():
            department = (record or {}).get("department", "").strip()
            if name == "challans" and any(
                str(row.get("department", "")).strip() != department
                for row in (record or {}).get("violations_history", [])
            ):
                continue  # Mixed-department legacy cases require administrator review.
            bind.execute(table.update().where(table.c.id == identifier).values(department_id=names.get(department)))
    if bind.dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Audit events cannot be changed or deleted'; END; $$""")
        op.execute("""CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events
                      FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()""")
    elif bind.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER audit_no_{action.lower()} BEFORE {action} ON audit_events
                           BEGIN SELECT RAISE(ABORT, 'Audit events cannot be changed or deleted'); END""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER audit_append_only ON audit_events")
        op.execute("DROP FUNCTION reject_audit_mutation()")
    elif op.get_bind().dialect.name == "sqlite":
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER audit_no_{action}")
    op.drop_column("users", "token_version")
    for table in ("challans", "audit_events", "evidence", "government_sightings", "users"):
        with op.batch_alter_table(table) as batch:
            if table != "users":
                batch.drop_index(f"ix_{table}_department_id")
            batch.drop_constraint(f"fk_{table}_department", type_="foreignkey")
            batch.drop_column("department_id")
