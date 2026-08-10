"""Read-only checks against a configured real CalmWay database."""

import os

import pytest

from backend.app.db.connection import create_database_engine
from backend.app.repositories.database_repository import (
    REQUIRED_PUBLIC_TABLES,
    verify_database,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set DATABASE_URL to run the PostgreSQL/PostGIS integration test.",
)
def test_real_database_is_ready_for_calmway() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        result = verify_database(engine)
    finally:
        engine.dispose()

    assert result.connection_ok
    assert result.postgresql_version
    assert result.postgis_version
    assert result.required_tables == REQUIRED_PUBLIC_TABLES
    assert result.schema_ok
    assert result.missing_tables == ()
