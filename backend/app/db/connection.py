"""Lazy SQLAlchemy engine lifecycle for PostgreSQL/PostGIS."""

import os
from threading import Lock

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, NoSuchModuleError

from ..config import SETTINGS
from .exceptions import DatabaseConfigurationError


_engine: Engine | None = None
_engine_lock = Lock()


def _validated_database_url(database_url: str | None = None) -> URL:
    raw_url = SETTINGS.database_url if database_url is None else database_url
    if not raw_url or not raw_url.strip():
        raise DatabaseConfigurationError(
            "DATABASE_URL is not configured. Set it in the process environment "
            "or an ignored backend/.env file."
        )

    try:
        url = make_url(raw_url.strip())
    except ArgumentError:
        raise DatabaseConfigurationError(
            "DATABASE_URL is invalid. Expected a PostgreSQL SQLAlchemy URL."
        ) from None

    if url.get_backend_name() != "postgresql":
        raise DatabaseConfigurationError(
            "DATABASE_URL must use PostgreSQL; SQLite and other databases are "
            "not supported."
        )

    # The handoff example uses PostgreSQL's generic URL. Select the installed
    # psycopg 3 driver explicitly when no SQLAlchemy driver was named.
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername != "postgresql+psycopg":
        raise DatabaseConfigurationError(
            "DATABASE_URL must use the psycopg 3 driver "
            "(postgresql+psycopg://...)."
        )

    return url


def create_database_engine(database_url: str | None = None) -> Engine:
    """Build an engine without opening a network connection."""

    url = _validated_database_url(database_url)
    engine_options: dict[str, object] = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 5},
    }
    if os.getenv("VERCEL") == "1":
        # Retain one reusable connection per warm function instance. This
        # avoids SQLAlchemy's default five-connection long-lived pool while
        # leaving connection multiplexing to the configured Neon pooler.
        engine_options.update(
            pool_size=1,
            max_overflow=0,
            pool_recycle=300,
        )
    try:
        return create_engine(url, **engine_options)
    except (ImportError, NoSuchModuleError):
        raise DatabaseConfigurationError(
            "The SQLAlchemy psycopg driver is unavailable. Install the backend "
            "requirements."
        ) from None


def get_database_engine() -> Engine:
    """Return the process-wide engine, creating it only on first use."""

    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = create_database_engine()
    return _engine


def dispose_engine() -> None:
    """Close pooled connections and clear the cached engine."""

    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
            _engine = None
