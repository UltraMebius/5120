"""Explicit small-range City CSV -> parser -> PostgreSQL integration."""

from datetime import date
import os

import pytest

from backend.app.db.connection import create_database_engine
from backend.app.repositories.hourly_count_repository import (
    HourlyCountRepository,
    inspect_hourly_import,
)
from backend.app.services.ingestion.city_hourly_client import (
    CityHourlyCountClient,
)
from backend.app.services.ingestion.hourly_count_ingestion import (
    HourlyCountIngestionService,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_LIVE = os.getenv("RUN_CITY_HOURLY_INTEGRATION", "") == "1"
TEST_DATE = date(2025, 1, 4)


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_LIVE,
    reason=(
        "Set DATABASE_URL and RUN_CITY_HOURLY_INTEGRATION=1 for the bounded "
        "City hourly/PostgreSQL integration test."
    ),
)
def test_live_bounded_hourly_export_can_be_upserted_and_verified() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        repository = HourlyCountRepository(engine)
        with CityHourlyCountClient() as client:
            result = HourlyCountIngestionService(client, repository).run(
                start_date=TEST_DATE,
                end_date=TEST_DATE,
            )
        verification = inspect_hourly_import(TEST_DATE, TEST_DATE, engine)
    finally:
        engine.dispose()

    assert result.source_rows_fetched > 0
    assert result.zero_count_rows > 0
    assert verification.row_count == result.database_eligible_rows
    assert verification.zero_count_rows == result.zero_count_rows
    assert verification.ok
