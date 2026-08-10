"""Gated rollback-only route sampling -> point crowd -> PostGIS integration."""

import os

import pytest
from sqlalchemy import text

from backend.app.db.connection import create_database_engine
from backend.app.repositories.spatial_repository import SpatialRepository
from backend.app.services.crowd.spatial_crowd_service import SpatialCrowdService
from backend.app.services.routing.route_crowd_evaluation_service import (
    RouteCrowdEvaluationService,
)
from backend.app.services.routing.route_sampling_service import RouteSamplingService


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_ROUTE_CROWD = os.getenv("RUN_ROUTE_CROWD_INTEGRATION", "") == "1"
TEST_IDS = (9_998_001, 9_998_002)
LONGITUDE = 144.2
LATITUDE = -38.8


_INTEGRITY_QUERY = text(
    """
    SELECT
        (SELECT COUNT(*) FROM pedestrian_hourly_count) hourly_rows,
        (SELECT COUNT(*) FROM sensor_hour_daytype_baseline) local_rows,
        (SELECT COUNT(*) FROM network_hour_daytype_baseline) network_rows,
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


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_ROUTE_CROWD,
    reason=(
        "Set DATABASE_URL and RUN_ROUTE_CROWD_INTEGRATION=1 to run the "
        "rollback-only route sample crowd integration."
    ),
)
def test_controlled_route_samples_propagate_supported_limited_and_no_data() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            before = connection.execute(_INTEGRITY_QUERY).mappings().one()

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
                                110.0,
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
                            'OK', :calculated_at
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
                            "calculated_at": calculated_at,
                        },
                        {
                            "location_id": TEST_IDS[1],
                            "window_start": window_start,
                            "window_end": window_end,
                            "crowd_score": 80.0,
                            "local_score": 70.0,
                            "calculated_at": calculated_at,
                        },
                    ],
                )

                endpoint = connection.execute(
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
                                650.0,
                                RADIANS(90.0)
                            ) AS geom
                        ) projected
                        """
                    ),
                    {"longitude": LONGITUDE, "latitude": LATITUDE},
                ).mappings().one()
                geometry = {
                    "type": "LineString",
                    "coordinates": [
                        [LONGITUDE, LATITUDE],
                        [float(endpoint["longitude"]), float(endpoint["latitude"])],
                    ],
                }
                spatial_service = SpatialCrowdService(
                    SpatialRepository(connection=connection)
                )
                evaluation = RouteCrowdEvaluationService(
                    RouteSamplingService(),
                    spatial_service,
                ).evaluate_geometry(geometry, route_id="controlled-route")

                assert evaluation.route_id == "controlled-route"
                assert evaluation.sample_count == 14
                assert [row.sample.index for row in evaluation.sample_results] == (
                    list(range(14))
                )
                assert [
                    row.sample.distance_along_route_meters
                    for row in evaluation.sample_results
                ] == sorted(
                    row.sample.distance_along_route_meters
                    for row in evaluation.sample_results
                )
                assert all(
                    row.sample.longitude == row.crowd.longitude
                    and row.sample.latitude == row.crowd.latitude
                    for row in evaluation.sample_results
                )

                coverage_counts = {
                    status: sum(
                        row.crowd.coverage_status == status
                        for row in evaluation.sample_results
                    )
                    for status in ("SUPPORTED", "LIMITED", "NO_DATA")
                }
                assert coverage_counts == {
                    "SUPPORTED": 8,
                    "LIMITED": 1,
                    "NO_DATA": 5,
                }

                first = evaluation.sample_results[0].crowd
                assert first.coverage_status == "SUPPORTED"
                assert first.supporting_sensors == 2
                expected_first_score = sum(
                    contribution.crowd_exposure_score
                    / max(contribution.distance_m, 1.0)
                    for contribution in first.contributions
                ) / sum(
                    1.0 / max(contribution.distance_m, 1.0)
                    for contribution in first.contributions
                )
                assert first.crowd_exposure_score == pytest.approx(
                    expected_first_score
                )
                assert first.local_condition_score is not None

                limited = next(
                    row.crowd
                    for row in evaluation.sample_results
                    if row.crowd.coverage_status == "LIMITED"
                )
                assert 250 < limited.nearest_sensor_distance_m <= 300
                assert limited.crowd_exposure_score == pytest.approx(80.0)

                no_data_rows = [
                    row.crowd
                    for row in evaluation.sample_results
                    if row.crowd.coverage_status == "NO_DATA"
                ]
                assert len(no_data_rows) == 5
                assert all(
                    row.crowd_exposure_score is None
                    and row.crowd_level is None
                    and row.local_condition_score is None
                    and row.local_condition is None
                    for row in no_data_rows
                )
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
