"""Explicit rollback-only PostGIS -> current state -> point score integration."""

import os

import pytest
from sqlalchemy import text

from backend.app.db.connection import create_database_engine
from backend.app.repositories.spatial_repository import SpatialRepository
from backend.app.services.crowd.spatial_crowd_service import SpatialCrowdService


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_SPATIAL = os.getenv("RUN_SPATIAL_INTEGRATION", "") == "1"
TEST_IDS = (9_999_001, 9_999_002, 9_999_003, 9_999_004)
LONGITUDE = 144.2
LATITUDE = -38.8


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_SPATIAL,
    reason=(
        "Set DATABASE_URL and RUN_SPATIAL_INTEGRATION=1 to run the "
        "rollback-only PostGIS point scoring integration."
    ),
)
def test_postgis_distances_current_activity_and_weighted_point_score() -> None:
    engine = create_database_engine(DATABASE_URL)
    with engine.connect() as connection:
        before = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM pedestrian_hourly_count) hourly_rows,
                    (SELECT COUNT(*) FROM sensor_hour_daytype_baseline) local_rows,
                    (SELECT COUNT(*) FROM network_hour_daytype_baseline)
                        network_rows,
                    (SELECT COUNT(*) FROM current_sensor_activity) current_rows,
                    (SELECT COUNT(*) FROM spatial_activity_cache) cache_rows,
                    (SELECT MIN(current_15m_window_start)
                     FROM current_sensor_activity) window_start,
                    (SELECT MAX(current_15m_window_end)
                     FROM current_sensor_activity) window_end,
                    (SELECT MAX(calculated_at)
                     FROM current_sensor_activity) updated_at
                """
            )
        ).mappings().one()
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
                        :location_id, :location_type, :status,
                        :latitude, :longitude,
                        ST_SetSRID(
                            ST_MakePoint(:longitude, :latitude), 4326
                        )::geography
                    )
                    """
                ),
                [
                    {
                        "location_id": TEST_IDS[0],
                        "location_type": "Outdoor",
                        "status": "A",
                        "latitude": LATITUDE,
                        "longitude": LONGITUDE,
                    },
                    {
                        "location_id": TEST_IDS[2],
                        "location_type": "Indoor",
                        "status": "A",
                        "latitude": LATITUDE,
                        "longitude": LONGITUDE,
                    },
                    {
                        "location_id": TEST_IDS[3],
                        "location_type": "Outdoor",
                        "status": "A",
                        "latitude": LATITUDE,
                        "longitude": LONGITUDE,
                    },
                ],
            )
            connection.execute(
                text(
                    """
                    WITH projected AS (
                        SELECT ST_Project(
                            ST_SetSRID(
                                ST_MakePoint(:longitude, :latitude), 4326
                            )::geography,
                            100.0,
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
            window_start = before["window_start"]
            window_end = before["window_end"]
            calculated_at = before["updated_at"]
            assert window_start is not None
            assert window_end is not None
            assert calculated_at is not None
            connection.execute(
                text(
                    """
                    INSERT INTO current_sensor_activity (
                        location_id, current_15m_window_start,
                        current_15m_window_end,
                        current_15m_network_percentile,
                        current_crowd_exposure_score,
                        current_1h_local_historical_percentile,
                        data_state, calculated_at
                    ) VALUES (
                        :location_id, :window_start, :window_end,
                        :crowd_score, :crowd_score, :local_score,
                        :data_state, :calculated_at
                    )
                    """
                ),
                [
                    {
                        "location_id": TEST_IDS[0],
                        "window_start": window_start,
                        "window_end": window_end,
                        "crowd_score": 20.0,
                        "local_score": 30.0,
                        "data_state": "OK",
                        "calculated_at": calculated_at,
                    },
                    {
                        "location_id": TEST_IDS[1],
                        "window_start": window_start,
                        "window_end": window_end,
                        "crowd_score": 80.0,
                        "local_score": 70.0,
                        "data_state": "OK",
                        "calculated_at": calculated_at,
                    },
                    {
                        "location_id": TEST_IDS[2],
                        "window_start": window_start,
                        "window_end": window_end,
                        "crowd_score": 100.0,
                        "local_score": 100.0,
                        "data_state": "OK",
                        "calculated_at": calculated_at,
                    },
                    {
                        "location_id": TEST_IDS[3],
                        "window_start": window_start,
                        "window_end": window_end,
                        "crowd_score": None,
                        "local_score": None,
                        "data_state": "AMBIGUOUS_NO_RECORD",
                        "calculated_at": calculated_at,
                    },
                ],
            )

            service = SpatialCrowdService(
                SpatialRepository(connection=connection)
            )
            first = service.evaluate(longitude=LONGITUDE, latitude=LATITUDE)
            second = service.evaluate(longitude=LONGITUDE, latitude=LATITUDE)

            assert first == second
            assert first.coverage_status == "SUPPORTED"
            assert first.supporting_sensors == 2
            assert first.nearest_sensor_distance_m == pytest.approx(0.0, abs=0.01)
            assert [row.location_id for row in first.contributions] == list(
                TEST_IDS[:2]
            )
            assert first.contributions[1].distance_m == pytest.approx(
                100.0, abs=0.02
            )
            expected = (
                20.0 / 1.0 + 80.0 / first.contributions[1].distance_m
            ) / (1.0 / 1.0 + 1.0 / first.contributions[1].distance_m)
            assert first.crowd_exposure_score == pytest.approx(expected)

            midpoint = connection.execute(
                text(
                    """
                    SELECT
                        ST_X(geom::geometry) AS longitude,
                        ST_Y(geom::geometry) AS latitude
                    FROM (
                        SELECT ST_Project(
                            ST_SetSRID(
                                ST_MakePoint(:longitude, :latitude), 4326
                            )::geography,
                            50.0,
                            RADIANS(90.0)
                        ) AS geom
                    ) projected
                    """
                ),
                {"longitude": LONGITUDE, "latitude": LATITUDE},
            ).mappings().one()
            multi_sensor = service.evaluate(
                longitude=float(midpoint["longitude"]),
                latitude=float(midpoint["latitude"]),
            )
            assert multi_sensor.coverage_status == "SUPPORTED"
            assert multi_sensor.supporting_sensors == 2
            assert multi_sensor.nearest_sensor_distance_m == pytest.approx(
                50.0, abs=0.02
            )
            assert multi_sensor.crowd_exposure_score == pytest.approx(50.0, abs=0.02)
            assert multi_sensor.local_condition_score == pytest.approx(50.0, abs=0.02)

            far_point = connection.execute(
                text(
                    """
                    SELECT
                        ST_X(geom::geometry) AS longitude,
                        ST_Y(geom::geometry) AS latitude
                    FROM (
                        SELECT ST_Project(
                            ST_SetSRID(
                                ST_MakePoint(:longitude, :latitude), 4326
                            )::geography,
                            500.0,
                            RADIANS(270.0)
                        ) AS geom
                    ) projected
                    """
                ),
                {"longitude": LONGITUDE, "latitude": LATITUDE},
            ).mappings().one()
            unsupported = service.evaluate(
                longitude=float(far_point["longitude"]),
                latitude=float(far_point["latitude"]),
            )
            assert unsupported.coverage_status == "NO_DATA"
            assert unsupported.crowd_exposure_score is None
            assert unsupported.crowd_level is None
            assert unsupported.nearest_sensor_distance_m > 300
        finally:
            transaction.rollback()

    with engine.connect() as connection:
        after = connection.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM pedestrian_hourly_count) hourly_rows,
                    (SELECT COUNT(*) FROM sensor_hour_daytype_baseline) local_rows,
                    (SELECT COUNT(*) FROM network_hour_daytype_baseline)
                        network_rows,
                    (SELECT COUNT(*) FROM current_sensor_activity) current_rows,
                    (SELECT COUNT(*) FROM spatial_activity_cache) cache_rows,
                    (SELECT MIN(current_15m_window_start)
                     FROM current_sensor_activity) window_start,
                    (SELECT MAX(current_15m_window_end)
                     FROM current_sensor_activity) window_end,
                    (SELECT MAX(calculated_at)
                     FROM current_sensor_activity) updated_at,
                    (SELECT COUNT(*) FROM sensor
                     WHERE location_id = ANY(CAST(:test_ids AS BIGINT[]))) test_rows
                """
            ),
            {"test_ids": list(TEST_IDS)},
        ).mappings().one()
    engine.dispose()

    assert dict(after) == {**dict(before), "test_rows": 0}
