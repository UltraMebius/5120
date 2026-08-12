"""Gated rollback-only batched PostGIS pedestrian-flow integration."""

from datetime import date
import os
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from backend.app.db.connection import create_database_engine
from backend.app.models.pedestrian_flow import FlowSamplePoint
from backend.app.repositories.pedestrian_flow_repository import (
    PedestrianFlowRepository,
)
from backend.app.services.crowd.pedestrian_flow_service import (
    PedestrianFlowService,
)


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_INTEGRATION = os.getenv("RUN_PEDESTRIAN_FLOW_INTEGRATION", "") == "1"
TEST_IDS = (9_997_001, 9_997_002)
LONGITUDE = 144.2
LATITUDE = -38.8


_INTEGRITY_QUERY = text(
    """
    SELECT
        (SELECT COUNT(*) FROM sensor) sensor_rows,
        (SELECT COUNT(*) FROM sensor_location_current) location_rows,
        (SELECT COUNT(*) FROM sensor_hour_daytype_baseline) baseline_rows,
        (SELECT COUNT(*) FROM current_sensor_activity) current_rows,
        (SELECT MIN(current_15m_window_start)
         FROM current_sensor_activity) window_start,
        (SELECT MAX(current_15m_window_end)
         FROM current_sensor_activity) window_end,
        (SELECT MAX(calculated_at)
         FROM current_sensor_activity) calculated_at
    """
)


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_INTEGRATION,
    reason=(
        "Set DATABASE_URL and RUN_PEDESTRIAN_FLOW_INTEGRATION=1 to run the "
        "rollback-only batched pedestrian-flow integration."
    ),
)
def test_batch_query_uses_controlled_current_and_baseline_rows_then_rolls_back() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            before = connection.execute(_INTEGRITY_QUERY).mappings().one()
        if (
            before["window_start"] is None
            or before["window_end"] is None
            or before["calculated_at"] is None
        ):
            pytest.skip("A current materialised window is required for this test.")

        local_window = before["window_start"].astimezone(
            ZoneInfo("Australia/Melbourne")
        )
        hour_day = local_window.hour
        day_type = (
            "Weekday" if local_window.isoweekday() <= 5 else "Weekend"
        )

        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    text("INSERT INTO sensor (location_id) VALUES (:location_id)"),
                    [{"location_id": location_id} for location_id in TEST_IDS],
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO sensor_location_current (
                            location_id, location_type, status,
                            latitude, longitude, geom
                        ) VALUES (
                            :location_id, 'Outdoor', 'A',
                            :latitude, :longitude,
                            ST_SetSRID(
                                ST_MakePoint(:longitude, :latitude), 4326
                            )::geography
                        )
                        """
                    ),
                    {
                        "location_id": TEST_IDS[0],
                        "longitude": LONGITUDE,
                        "latitude": LATITUDE,
                    },
                )
                connection.execute(
                    text(
                        """
                        WITH projected AS (
                            SELECT ST_Project(
                                ST_SetSRID(
                                    ST_MakePoint(:longitude, :latitude), 4326
                                )::geography,
                                200.0,
                                RADIANS(90.0)
                            ) AS geom
                        )
                        INSERT INTO sensor_location_current (
                            location_id, location_type, status,
                            latitude, longitude, geom
                        )
                        SELECT
                            :location_id, 'Outdoor', 'A',
                            ST_Y(geom::geometry), ST_X(geom::geometry), geom
                        FROM projected
                        """
                    ),
                    {
                        "location_id": TEST_IDS[1],
                        "longitude": LONGITUDE,
                        "latitude": LATITUDE,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO current_sensor_activity (
                            location_id,
                            current_15m_window_start,
                            current_15m_window_end,
                            current_15m_observed_rows,
                            current_15m_count,
                            data_state,
                            calculated_at
                        ) VALUES (
                            :location_id,
                            :window_start,
                            :window_end,
                            :observed_rows,
                            :current_count,
                            'OK',
                            :calculated_at
                        )
                        """
                    ),
                    [
                        {
                            "location_id": TEST_IDS[0],
                            "window_start": before["window_start"],
                            "window_end": before["window_end"],
                            "observed_rows": 5,
                            "current_count": 150,
                            "calculated_at": before["calculated_at"],
                        },
                        {
                            "location_id": TEST_IDS[1],
                            "window_start": before["window_start"],
                            "window_end": before["window_end"],
                            "observed_rows": 15,
                            "current_count": 450,
                            "calculated_at": before["calculated_at"],
                        },
                    ],
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO sensor_hour_daytype_baseline (
                            location_id, hour_day, day_type,
                            observation_count, mean_count, median_count, p75,
                            baseline_start_date, baseline_end_date
                        ) VALUES (
                            :location_id, :hour_day, :day_type,
                            50, :mean_count, :median_count, :p75,
                            :baseline_start_date, :baseline_end_date
                        )
                        """
                    ),
                    [
                        {
                            "location_id": TEST_IDS[0],
                            "hour_day": hour_day,
                            "day_type": day_type,
                            "mean_count": 720.0,
                            "median_count": 600.0,
                            "p75": 900.0,
                            "baseline_start_date": date(2024, 8, 10),
                            "baseline_end_date": date(2026, 2, 7),
                        },
                        {
                            "location_id": TEST_IDS[1],
                            "hour_day": hour_day,
                            "day_type": day_type,
                            "mean_count": 1920.0,
                            "median_count": 1800.0,
                            "p75": 2100.0,
                            "baseline_start_date": date(2024, 8, 10),
                            "baseline_end_date": date(2026, 2, 7),
                        },
                    ],
                )

                samples = tuple(
                    FlowSamplePoint(
                        route_index=route_index,
                        sample_index=0,
                        distance_along_route_meters=0.0,
                        longitude=LONGITUDE,
                        latitude=LATITUDE,
                    )
                    for route_index in (0, 1, 2)
                )
                result = PedestrianFlowService(
                    PedestrianFlowRepository(connection=connection)
                ).evaluate_samples(samples)

                assert result.sql_execution_count == 1
                assert [row.route_index for row in result.samples] == [0, 1, 2]
                for sample in result.samples:
                    assert sample.live_contributor_count == 2
                    assert sample.historical_contributor_count == 2
                    expected_live = sum(
                        row.pedestrian_movements_per_minute
                        * row.normalised_weight
                        for row in sample.live_contributions
                    )
                    expected_historical = sum(
                        row.pedestrian_movements_per_minute
                        * row.normalised_weight
                        for row in sample.historical_contributions
                    )
                    assert (
                        sample.live_pedestrian_movements_per_minute
                        == pytest.approx(expected_live)
                    )
                    assert (
                        sample.historical_typical_movements_per_minute
                        == pytest.approx(expected_historical)
                    )
                    assert sample.live_contributions[0].distance_meters < 1.0
                    assert sample.live_contributions[0].normalised_weight > 0.99
            finally:
                transaction.rollback()

        with engine.connect() as connection:
            after = connection.execute(_INTEGRITY_QUERY).mappings().one()
            test_rows = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM sensor
                    WHERE location_id = ANY(CAST(:test_ids AS BIGINT[]))
                    """
                ),
                {"test_ids": list(TEST_IDS)},
            ).scalar_one()

        assert dict(after) == dict(before)
        assert test_rows == 0
    finally:
        engine.dispose()
