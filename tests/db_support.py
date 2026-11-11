import os
import re

from sqlalchemy import text, select
from sqlalchemy.engine import make_url

from backend.database import Base, make_engine
from backend import db_models


def make_test_engine():
    """A new SQLite database, or clean data inside the runner's private PG schema."""
    url = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    engine = make_engine(url)
    if engine.dialect.name == "postgresql":
        options = make_url(url).query.get("options", "")
        if not re.fullmatch(r"-csearch_path=test_[a-f0-9]{32}", options):
            engine.dispose()
            raise RuntimeError("PostgreSQL tests require a private schema created by backend.test_runner")
        # Keep users and migration version; application connection uses this schema too.
        with engine.begin() as connection:
            accounts = [dict(row) for row in connection.execute(select(db_models.User.__table__).where(
                db_models.User.email.in_([f"{role}@justmeter.gov" for role in ("admin", "transport", "supervisor", "auditor")]))).mappings()]
            tables = [table.name for table in Base.metadata.sorted_tables if table.name != "users"]
            connection.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
            # users now reference departments, so PostgreSQL CASCADE truncates them too.
            for row in accounts:
                row.update(department_id=None, token_version=0)
            if accounts:
                connection.execute(db_models.User.__table__.insert(), accounts)
                connection.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT max(id) FROM users))"))
    else:
        Base.metadata.create_all(engine)
    return engine


def authenticated_headers(store, role="Administrator", email="user@test", department_id=None):
    """Create a real account: signed tokens alone no longer authorize requests."""
    from backend.auth import create_access_token
    with store._lock as session:
        if department_id is None and role in {"Transport Officer", "Supervisory Officer"}:
            department_id = session.scalar(select(db_models.Department.id).order_by(db_models.Department.id).limit(1))
        user = session.scalar(select(db_models.User).where(db_models.User.email == email))
        if user is None:
            user = db_models.User(email=email, password_hash="unused-by-token-tests", token_version=0)
            session.add(user)
        user.name, user.role, user.active, user.department_id = role, role, True, department_id
        session.flush()
        token = create_access_token({"email": email, "name": role, "role": role, "token_version": user.token_version})
    return {"Authorization": "Bearer " + token}
