from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


# Ensure DB directory exists (only for file-based SQLite, not :memory:)
_db_url = settings.database_url
if "sqlite" in _db_url and ":memory:" not in _db_url:
    _db_path = _db_url.replace("sqlite:///", "")
    _db_dir = os.path.dirname(os.path.abspath(_db_path))
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)


_is_memory = ":memory:" in settings.database_url

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    poolclass=StaticPool if _is_memory else None,
    echo=settings.debug,
)

# Enable WAL mode for SQLite (better concurrent read performance)
if "sqlite" in settings.database_url:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables."""
    from app.models import db_models  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)
    log.info("Database initialised")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-manager session for use outside request context."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
