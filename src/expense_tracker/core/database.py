"""SQLAlchemy engine and session management.

The engine is created lazily so importing this module has no side effects
(no directories are created, no files are opened).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from expense_tracker.config import get_settings


class Base(DeclarativeBase):
    """Base class for ORM models."""


_lock = Lock()
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_database(url: str | None = None) -> Engine:
    """(Re)initialise the engine. ``url`` defaults to the configured SQLite file."""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        settings = get_settings()
        if url is None:
            settings.db_path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
            url = settings.database_url
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
            pool_pre_ping=True,
        )
        if url.startswith("sqlite"):
            event.listen(engine, "connect", _sqlite_pragmas)
        _engine = engine
        _session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        return engine


def _sqlite_pragmas(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine() -> Engine:
    if _engine is None:
        return configure_database()
    return _engine


def init_db() -> None:
    """Create tables that do not exist yet."""
    from expense_tracker.core import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session: commit on success, roll back on error."""
    get_engine()
    assert _session_factory is not None  # noqa: S101 - set by get_engine()
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
