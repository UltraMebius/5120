from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.app.db.connection import create_database_engine
from backend.app.db.exceptions import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    DatabaseSchemaError,
    PostGISUnavailableError,
)
from backend.app.repositories.database_repository import (
    REQUIRED_PUBLIC_TABLES,
    inspect_database,
    verify_database,
)


def _result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _engine_with_results(
    *,
    tables: tuple[str, ...] = REQUIRED_PUBLIC_TABLES,
) -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    table_result = MagicMock()
    table_result.scalars.return_value = iter(tables)
    connection.execute.side_effect = [
        _result(1),
        _result("16.4"),
        _result("3.4.3"),
        table_result,
    ]
    return engine, connection


def test_database_engine_requires_a_url() -> None:
    with pytest.raises(DatabaseConfigurationError, match="not configured"):
        create_database_engine(" ")


def test_database_engine_rejects_sqlite() -> None:
    with pytest.raises(DatabaseConfigurationError, match="must use PostgreSQL"):
        create_database_engine("sqlite:///calmway.db")


def test_database_engine_is_lazy_and_normalizes_generic_postgresql_url() -> None:
    engine = create_database_engine(
        "postgresql://example-user:example-password@localhost:5432/example"
    )

    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


def test_database_inspection_runs_all_read_only_checks() -> None:
    engine, connection = _engine_with_results()

    result = inspect_database(engine)

    assert result.connection_ok
    assert result.postgresql_version == "16.4"
    assert result.postgis_version == "3.4.3"
    assert result.schema_ok
    assert result.missing_tables == ()
    statements = [str(call.args[0]) for call in connection.execute.call_args_list]
    assert "SELECT 1" in statements[0]
    assert "server_version" in statements[1]
    assert "PostGIS_Lib_Version" in statements[2]
    assert "information_schema.tables" in statements[3]


def test_schema_error_lists_only_missing_required_tables() -> None:
    present_tables = tuple(
        table for table in REQUIRED_PUBLIC_TABLES if table != "landmark"
    )
    engine, _ = _engine_with_results(tables=present_tables)

    with pytest.raises(DatabaseSchemaError) as exc_info:
        verify_database(engine)

    assert exc_info.value.missing_tables == ("landmark",)


def test_connection_failure_is_sanitized() -> None:
    engine = MagicMock()
    engine.connect.side_effect = SQLAlchemyError(
        "postgresql://user:secret-password@localhost/epic1"
    )

    with pytest.raises(DatabaseConnectionError) as exc_info:
        inspect_database(engine)

    assert "secret-password" not in str(exc_info.value)


def test_postgis_failure_is_distinguishable_and_sanitized() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.side_effect = [
        _result(1),
        _result("16.4"),
        SQLAlchemyError("secret-password"),
    ]

    with pytest.raises(PostGISUnavailableError) as exc_info:
        inspect_database(engine)

    assert "PostGIS verification failed" in str(exc_info.value)
    assert "secret-password" not in str(exc_info.value)
