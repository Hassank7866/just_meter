"""Run tests with disposable database schemas and temporary image storage.

docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
"""
import argparse
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from . import database
from .bootstrap import seed_users
from .config import PROJECT_ROOT, settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres", action="store_true")
    args = parser.parse_args()
    os.environ["AUTH_JWT_SECRET"] = "isolated-test-secret-not-for-deployment"
    for role in ("ADMIN", "TRANSPORT", "SUPERVISOR", "AUDITOR"):
        os.environ.pop(f"DEMO_{role}_PASSWORD", None)
    admin_engine = None
    schema = None
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, relative in {
            "data_dir": ".", "snapshots_dir": "snapshots", "csv_path": "detections.csv",
            "approved_vehicles_path": "approved_government_vehicles.csv",
            "government_sightings_path": "government_vehicles_spotted.csv",
            "vehicle_events_path": "vehicle_detection_events.csv", "plate_recognition_path": "plate_recognition_events.csv",
            "plate_crops_dir": "snapshots/plates", "evidence_path": "evidence_records.csv",
            "evidence_images_dir": "snapshots/evidence",
        }.items():
            object.__setattr__(settings, name, root / relative)
        settings.snapshots_dir.mkdir()
        try:
            if args.postgres:
                url = make_url(os.environ["DATABASE_URL"])
                admin_engine = database.make_engine(url.render_as_string(hide_password=False))
                schema = "test_" + uuid4().hex
                with admin_engine.begin() as connection:
                    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                url = url.update_query_dict({"options": f"-csearch_path={schema}"})
                os.environ["TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
            else:
                os.environ["TEST_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
            database._engine = database.make_engine(os.environ["TEST_DATABASE_URL"])
            command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
            seed_users(database._engine)
            suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1
        finally:
            if database._engine:
                database._engine.dispose()
                database._engine = None
            if admin_engine and schema:
                with admin_engine.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
