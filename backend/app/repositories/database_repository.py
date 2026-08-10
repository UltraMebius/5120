"""Read-only PostgreSQL/PostGIS and CalmWay schema verification."""

from dataclasses import dataclass

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from ..db.connection import get_database_engine
from ..db.exceptions import (
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseSchemaError,
    PostGISUnavailableError,
)


# Every base table created by the authoritative 05_DATABASE_SCHEMA.sql. The two
# v_minute_* objects are views, so they are deliberately not treated as tables.
REQUIRED_PUBLIC_TABLES: tuple[str, ...] = (
    "sensor",
    "sensor_location_current",
    "pedestrian_hourly_count",
    "ingestion_run",
    "pedestrian_minute_observation_raw",
    "sensor_hour_daytype_baseline",
    "network_hour_daytype_baseline",
    "current_sensor_activity",
    "theme",
    "sub_theme",
    "landmark",
    "spatial_activity_cache",
)


@dataclass(frozen=True)
class DatabaseVerificationResult:
    """Successful read-only database inspection result."""

    postgresql_version: str
    postgis_version: str
    required_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]

    @property
    def connection_ok(self) -> bool:
        return True

    @property
    def schema_ok(self) -> bool:
        return not self.missing_tables


def inspect_database(engine: Engine | None = None) -> DatabaseVerificationResult:
    """Run connectivity, version, PostGIS, and public-table checks."""

    database_engine = engine or get_database_engine()
    try:
        connection_context = database_engine.connect()
    except SQLAlchemyError:
        raise DatabaseConnectionError(
            "Database connection failed. Check that PostgreSQL is running and "
            "DATABASE_URL is correct."
        ) from None

    with connection_context as connection:
        try:
            probe = connection.execute(text("SELECT 1")).scalar_one()
            postgresql_version = connection.execute(
                text("SELECT current_setting('server_version')")
            ).scalar_one()
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "PostgreSQL connected, but the basic verification query failed."
            ) from None

        if probe != 1:
            raise DatabaseQueryError(
                "PostgreSQL returned an unexpected connectivity-check result."
            )

        try:
            postgis_version = connection.execute(
                text("SELECT PostGIS_Lib_Version()")
            ).scalar_one()
        except SQLAlchemyError:
            raise PostGISUnavailableError(
                "PostGIS verification failed. Ensure the PostGIS extension is "
                "installed in the configured database."
            ) from None

        if not postgis_version:
            raise PostGISUnavailableError(
                "PostGIS verification returned no version. Ensure the PostGIS "
                "extension is installed in the configured database."
            )

        try:
            table_names = connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                      AND table_type = 'BASE TABLE'
                    """
                ),
                {"schema_name": "public"},
            ).scalars()
            available_tables = set(table_names)
        except SQLAlchemyError:
            raise DatabaseQueryError(
                "PostgreSQL connected, but public schema inspection failed."
            ) from None

    missing_tables = tuple(
        table_name
        for table_name in REQUIRED_PUBLIC_TABLES
        if table_name not in available_tables
    )
    return DatabaseVerificationResult(
        postgresql_version=str(postgresql_version),
        postgis_version=str(postgis_version),
        required_tables=REQUIRED_PUBLIC_TABLES,
        missing_tables=missing_tables,
    )


def verify_database(engine: Engine | None = None) -> DatabaseVerificationResult:
    """Return a report only when PostgreSQL, PostGIS, and the schema are ready."""

    result = inspect_database(engine)
    if result.missing_tables:
        raise DatabaseSchemaError(result.missing_tables)
    return result
