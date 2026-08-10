"""Database lifecycle boundary for the authoritative PostGIS schema."""

from .connection import (
    create_database_engine,
    dispose_engine,
    get_database_engine,
)
from .exceptions import (
    CalmWayDatabaseError,
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseSchemaError,
    DatabaseWriteError,
    PostGISUnavailableError,
)

__all__ = [
    "CalmWayDatabaseError",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    "DatabaseSchemaError",
    "DatabaseWriteError",
    "PostGISUnavailableError",
    "create_database_engine",
    "dispose_engine",
    "get_database_engine",
]
