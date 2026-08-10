"""Sanitized database-layer errors safe to show in developer tools."""


class CalmWayDatabaseError(RuntimeError):
    """Base class for expected CalmWay database failures."""


class DatabaseConfigurationError(CalmWayDatabaseError):
    """Raised when DATABASE_URL is missing or unsupported."""


class DatabaseConnectionError(CalmWayDatabaseError):
    """Raised when PostgreSQL cannot be reached."""


class DatabaseQueryError(CalmWayDatabaseError):
    """Raised when a database inspection query cannot be completed."""


class PostGISUnavailableError(CalmWayDatabaseError):
    """Raised when the required PostGIS extension cannot be verified."""


class DatabaseSchemaError(CalmWayDatabaseError):
    """Raised when required CalmWay tables are absent."""

    def __init__(self, missing_tables: tuple[str, ...]) -> None:
        self.missing_tables = missing_tables
        table_list = ", ".join(missing_tables)
        super().__init__(f"Required public schema tables are missing: {table_list}")
