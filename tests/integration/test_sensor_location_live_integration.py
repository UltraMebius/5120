"""Explicitly enabled City API -> parser -> local PostGIS integration test."""

import os

import pytest

from backend.app.db.connection import create_database_engine
from backend.app.repositories.sensor_repository import (
    SensorRepository,
    inspect_sensor_import,
)
from backend.app.services.ingestion.city_sensor_client import (
    CitySensorLocationClient,
)
from backend.app.services.ingestion.sensor_location_ingestion import (
    SensorLocationIngestionService,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_LIVE = os.getenv("RUN_CITY_SENSOR_INTEGRATION", "") == "1"


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_LIVE,
    reason=(
        "Set DATABASE_URL and RUN_CITY_SENSOR_INTEGRATION=1 to run the live "
        "City API/PostGIS integration test."
    ),
)
def test_live_city_sensor_snapshot_can_be_upserted_and_verified() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        with CitySensorLocationClient() as client:
            result = SensorLocationIngestionService(
                client, SensorRepository(engine)
            ).run()
        verification = inspect_sensor_import(result.validation.records, engine)
    finally:
        engine.dispose()

    assert len(result.snapshot.records) > 0
    assert len(result.validation.records) > 0
    assert verification.ok
