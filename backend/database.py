"""Database connections; PostgreSQL in Compose, isolated SQLite only in tests."""
from __future__ import annotations

import os
from contextlib import contextmanager
from threading import RLock, local

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    options = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options.update(connect_args={"check_same_thread": False})
        if ":memory:" in url:
            options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required. Start the application with Docker Compose.")
        _engine = make_engine(url)
    return _engine


class TransactionLock:
    """Serialize pilot writes across workers; nested calls share one transaction.

    The advisory lock also makes cooldown, history counting, and risk/task writes
    atomic across processes. Sessions are thread-local, never shared by requests.
    """
    def __init__(self, engine):
        self.engine = engine
        self.mutex = RLock()
        self.state = local()

    def __enter__(self):
        self.mutex.acquire()
        depth = getattr(self.state, "depth", 0)
        try:
            if depth == 0:
                self.state.session = Session(self.engine, expire_on_commit=False)
                self.state.session.begin()
                if self.engine.dialect.name == "postgresql":
                    self.state.session.execute(text("SELECT pg_advisory_xact_lock(918710)"))
            self.state.depth = depth + 1
            return self.state.session
        except Exception:
            if getattr(self.state, "session", None):
                self.state.session.close()
            self.mutex.release()
            raise

    def __exit__(self, kind, value, traceback):
        self.state.depth -= 1
        try:
            if self.state.depth == 0:
                try:
                    if kind:
                        self.state.session.rollback()
                    else:
                        self.state.session.commit()
                finally:
                    self.state.session.close()
                    self.state.session = None
        finally:
            self.mutex.release()

    @contextmanager
    def session(self):
        with self as session:
            yield session
