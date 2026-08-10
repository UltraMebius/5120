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
    PostGISUnavailableError,
)

__all__ = [
    "CalmWayDatabaseError",
    "DatabaseConfigurationError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    "DatabaseSchemaError",
    "PostGISUnavailableError",
    "create_database_engine",
    "dispose_engine",
    "get_database_engine",
]
