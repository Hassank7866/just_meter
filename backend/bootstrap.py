"""Container startup: schema migrations, legacy import, then initial demo accounts."""
import json
import os

import bcrypt
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from .config import PROJECT_ROOT, settings
from .database import get_engine, TransactionLock
from .db_models import User


def seed_users(engine):
    accounts = [
        ("admin", "System Administrator", "Administrator", "DEMO_ADMIN_PASSWORD", "admin123"),
        ("transport", "Transport Officer", "Transport Officer", "DEMO_TRANSPORT_PASSWORD", "transport123"),
        ("supervisor", "Supervisory Officer", "Supervisory Officer", "DEMO_SUPERVISOR_PASSWORD", "supervisor123"),
        ("auditor", "Auditor", "Auditor", "DEMO_AUDITOR_PASSWORD", "auditor123"),
    ]
    with TransactionLock(engine) as session:
        for prefix, name, role, variable, default in accounts:
            email = f"{prefix}@justmeter.gov"
            if session.scalar(select(User.id).where(User.email == email)) is None:
                password = os.getenv(variable, default).encode("utf-8")
                session.add(User(email=email, name=name, role=role,
                    password_hash=bcrypt.hashpw(password, bcrypt.gensalt()).decode("ascii")))


def initialize():
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    from .storage import DetectionStore
    from .migrate_legacy import import_legacy
    store = DetectionStore()
    if os.getenv("IMPORT_LEGACY_DATA", "true").lower() == "true":
        print(json.dumps({"legacy_import": import_legacy(store, settings.data_dir)}), flush=True)
    seed_users(get_engine())
    store.get_risk_policy()


if __name__ == "__main__":
    initialize()
