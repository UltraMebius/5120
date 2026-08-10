"""Explicit read-only SQL audit of the production-shaped raw/current layer."""

import os

import pytest
from sqlalchemy import text

from backend.app.db.connection import create_database_engine
from backend.app.repositories.current_activity_repository import (
    CurrentActivityRepository,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_CURRENT = os.getenv("RUN_CURRENT_ACTIVITY_INTEGRATION", "") == "1"


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_CURRENT,
    reason=(
        "Set DATABASE_URL and RUN_CURRENT_ACTIVITY_INTEGRATION=1 after a real "
        "refresh to audit raw/current activity."
    ),
)
def test_raw_minute_and_current_activity_database_invariants() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        verification = CurrentActivityRepository(engine).inspect_current_activity()
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT COUNT(*)
                         FROM pedestrian_minute_observation_raw) AS raw_rows,
                        (SELECT COUNT(*) FROM (
                            SELECT payload_hash
                            FROM pedestrian_minute_observation_raw
                            GROUP BY payload_hash HAVING COUNT(*) > 1
                         ) d) AS exact_payload_duplicate_groups,
                        (SELECT COUNT(*) FROM (
                            SELECT location_id, source_sensing_datetime
                            FROM pedestrian_minute_observation_raw
                            GROUP BY location_id, source_sensing_datetime
                            HAVING COUNT(DISTINCT payload_hash) > 1
                         ) d) AS logical_conflict_groups,
                        (SELECT COUNT(*) FROM v_minute_conflict_groups)
                            AS conflict_view_groups,
                        (SELECT COUNT(*)
                         FROM pedestrian_minute_observation_raw
                         WHERE total_of_directions < 0
                            OR direction_1 < 0 OR direction_2 < 0)
                            AS negative_raw_rows,
                        (SELECT COUNT(*) FROM current_sensor_activity
                         WHERE data_state = 'STALE'
                           AND (current_15m_count IS NOT NULL
                             OR current_crowd_exposure_score IS NOT NULL))
                            AS stale_numeric_rows,
                        (SELECT COUNT(*)
                         FROM current_sensor_activity a
                         JOIN sensor_location_current sl USING (location_id)
                         WHERE LOWER(BTRIM(sl.location_type)) = 'indoor'
                           AND a.data_state <> 'NO_DATA')
                            AS indoor_modelled_rows,
                        (SELECT COUNT(*) FROM current_sensor_activity
                         WHERE location_id IN (47, 181)
                           AND current_1h_local_historical_percentile IS NOT NULL)
                            AS forbidden_relocation_local_rows,
                        (SELECT COUNT(*) FROM ingestion_run
                         WHERE source_name = 'city_past_hour_counts_per_minute'
                           AND status = 'SUCCEEDED') AS successful_runs
                    """
                )
            ).mappings().one()
    finally:
        engine.dispose()

    assert int(row["raw_rows"]) > 0
    assert int(row["exact_payload_duplicate_groups"]) == 0
    assert int(row["logical_conflict_groups"]) == int(row["conflict_view_groups"])
    assert int(row["negative_raw_rows"]) == 0
    assert int(row["stale_numeric_rows"]) == 0
    assert int(row["indoor_modelled_rows"]) == 0
    assert int(row["forbidden_relocation_local_rows"]) == 0
    assert int(row["successful_runs"]) > 0
    assert verification.ok
