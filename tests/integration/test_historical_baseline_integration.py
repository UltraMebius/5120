"""Explicit full PostgreSQL hourly-facts -> baseline integration test."""

import os

import pytest
from sqlalchemy import text

from backend.app.db.connection import create_database_engine
from backend.app.repositories.baseline_repository import BaselineRepository
from backend.app.services.baseline.historical_baseline_service import (
    HistoricalBaselineService,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_BASELINES = os.getenv("RUN_BASELINE_INTEGRATION", "") == "1"


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_BASELINES,
    reason=(
        "Set DATABASE_URL and RUN_BASELINE_INTEGRATION=1 to rebuild and "
        "verify the two derived baseline tables."
    ),
)
def test_full_hourly_facts_build_idempotent_production_baselines() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        service = HistoricalBaselineService(BaselineRepository(engine))
        source = service.inspect_source()
        first = service.build()
        first_verification = first.verification
        second = service.build()
        second_verification = second.verification

        with engine.connect() as connection:
            contribution = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT SUM(observation_count)
                         FROM sensor_hour_daytype_baseline) AS local_rows,
                        (SELECT SUM(observation_count)
                         FROM network_hour_daytype_baseline) AS network_rows,
                        (SELECT SUM(observation_count)
                         FROM sensor_hour_daytype_baseline
                         WHERE location_id = 14) AS sensor_14_rows,
                        (SELECT SUM(observation_count)
                         FROM sensor_hour_daytype_baseline
                         WHERE location_id = 37) AS sensor_37_rows,
                        (SELECT COUNT(*)
                         FROM sensor_hour_daytype_baseline
                         WHERE location_id IN (47, 181, 28, 65, 78))
                            AS forbidden_local_rows
                    """
                )
            ).mappings().one()
    finally:
        engine.dispose()

    assert source.zero_count_rows > 0
    assert int(contribution["local_rows"]) == source.local_observation_count
    assert int(contribution["network_rows"]) == source.eligible_observation_count
    assert int(contribution["sensor_14_rows"]) == source.sensor_14_observation_count
    assert int(contribution["sensor_37_rows"]) == source.sensor_37_local_observation_count
    assert int(contribution["forbidden_local_rows"]) == 0
    assert first_verification.ok
    assert second_verification.ok
    assert first_verification.local_row_count == second_verification.local_row_count
    assert first_verification.network_row_count == second_verification.network_row_count
    assert (
        first_verification.local_logical_checksum
        == second_verification.local_logical_checksum
    )
    assert (
        first_verification.network_logical_checksum
        == second_verification.network_logical_checksum
    )
