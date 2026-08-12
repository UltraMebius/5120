"""Gated rollback-only PostGIS integration for route waypoint evidence."""

from datetime import date, datetime, timedelta, timezone
import os
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from backend.app.db.connection import create_database_engine
from backend.app.repositories.route_waypoint_repository import (
    RouteWaypointRepository,
)
from backend.app.schemas.routes import GeoJsonLineString


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
RUN_INTEGRATION = os.getenv("RUN_ROUTE_WAYPOINT_INTEGRATION", "") == "1"

LIVE_ID = 9_996_101
HISTORICAL_ID = 9_996_102
TOO_CLOSE_TO_ROUTE_ID = 9_996_103
TOO_CLOSE_TO_ORIGIN_ID = 9_996_104
TOO_CLOSE_TO_DESTINATION_ID = 9_996_105
INACTIVE_ID = 9_996_106
INDOOR_ID = 9_996_107
OUTSIDE_CORRIDOR_ID = 9_996_108
EXCESSIVE_GEOMETRIC_DETOUR_ID = 9_996_109
TEST_IDS = (
    LIVE_ID,
    HISTORICAL_ID,
    TOO_CLOSE_TO_ROUTE_ID,
    TOO_CLOSE_TO_ORIGIN_ID,
    TOO_CLOSE_TO_DESTINATION_ID,
    INACTIVE_ID,
    INDOOR_ID,
    OUTSIDE_CORRIDOR_ID,
    EXCESSIVE_GEOMETRIC_DETOUR_ID,
)

ORIGIN = (144.2, -38.8)
DIRECT_ROUTE_LENGTH_M = 1_000.0


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
         FROM current_sensor_activity) calculated_at,
        (SELECT COUNT(DISTINCT JSONB_BUILD_ARRAY(
             current_15m_window_start,
             current_15m_window_end
         )) FROM current_sensor_activity) window_variant_count
    """
)


@pytest.mark.skipif(
    not DATABASE_URL or not RUN_INTEGRATION,
    reason=(
        "Set DATABASE_URL and RUN_ROUTE_WAYPOINT_INTEGRATION=1 to run the "
        "rollback-only route waypoint PostGIS integration."
    ),
)
def test_controlled_waypoint_evidence_uses_real_postgis_then_rolls_back() -> None:
    engine = create_database_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            before = connection.execute(_INTEGRITY_QUERY).mappings().one()

        if before["window_variant_count"] > 1:
            pytest.skip(
                "A single current materialised window is required for this test."
            )

        if before["window_variant_count"] == 1:
            window_start = before["window_start"]
            window_end = before["window_end"]
            calculated_at = before["calculated_at"]
        else:
            window_start = datetime(2026, 8, 12, 23, 0, tzinfo=timezone.utc)
            window_end = window_start + timedelta(minutes=15)
            calculated_at = window_end + timedelta(minutes=5)

        assert window_start is not None
        assert window_end is not None
        assert calculated_at is not None
        local_window = window_start.astimezone(
            ZoneInfo("Australia/Melbourne")
        )
        hour_day = local_window.hour
        day_type = (
            "Weekday" if local_window.isoweekday() <= 5 else "Weekend"
        )

        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                destination = connection.execute(
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
                                :route_length_m,
                                RADIANS(0.0)
                            ) AS geom
                        ) projected
                        """
                    ),
                    {
                        "longitude": ORIGIN[0],
                        "latitude": ORIGIN[1],
                        "route_length_m": DIRECT_ROUTE_LENGTH_M,
                    },
                ).mappings().one()
                destination_coordinate = (
                    float(destination["longitude"]),
                    float(destination["latitude"]),
                )
                direct_route = GeoJsonLineString(
                    coordinates=[ORIGIN, destination_coordinate]
                )

                connection.execute(
                    text("INSERT INTO sensor (location_id) VALUES (:location_id)"),
                    [{"location_id": location_id} for location_id in TEST_IDS],
                )
                connection.execute(
                    text(
                        """
                        WITH route_position AS (
                            SELECT
                                CAST(:location_id AS BIGINT) AS location_id,
                                CAST(:location_type AS TEXT) AS location_type,
                                CAST(:status AS TEXT) AS status,
                                ST_Project(
                                    ST_SetSRID(
                                        ST_MakePoint(
                                            :origin_longitude,
                                            :origin_latitude
                                        ), 4326
                                    )::geography,
                                    :distance_along_route_m,
                                    RADIANS(0.0)
                                ) AS geom
                        ),
                        offset_position AS (
                            SELECT
                                location_id,
                                location_type,
                                status,
                                ST_Project(
                                    geom,
                                    :route_offset_m,
                                    RADIANS(:offset_bearing_degrees)
                                ) AS geom
                            FROM route_position
                        )
                        INSERT INTO sensor_location_current (
                            location_id,
                            location_type,
                            status,
                            latitude,
                            longitude,
                            geom
                        )
                        SELECT
                            location_id,
                            location_type,
                            status,
                            ST_Y(geom::geometry),
                            ST_X(geom::geometry),
                            geom
                        FROM offset_position
                        """
                    ),
                    [
                        {
                            "location_id": LIVE_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 100.0,
                            "offset_bearing_degrees": 90.0,
                        },
                        {
                            "location_id": HISTORICAL_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 200.0,
                            "offset_bearing_degrees": 270.0,
                        },
                        {
                            "location_id": TOO_CLOSE_TO_ROUTE_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 20.0,
                            "offset_bearing_degrees": 90.0,
                        },
                        {
                            "location_id": TOO_CLOSE_TO_ORIGIN_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 100.0,
                            "route_offset_m": 80.0,
                            "offset_bearing_degrees": 90.0,
                        },
                        {
                            "location_id": TOO_CLOSE_TO_DESTINATION_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 900.0,
                            "route_offset_m": 80.0,
                            "offset_bearing_degrees": 270.0,
                        },
                        {
                            "location_id": INACTIVE_ID,
                            "location_type": "Outdoor",
                            "status": "I",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 120.0,
                            "offset_bearing_degrees": 90.0,
                        },
                        {
                            "location_id": INDOOR_ID,
                            "location_type": "Indoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 140.0,
                            "offset_bearing_degrees": 270.0,
                        },
                        {
                            "location_id": OUTSIDE_CORRIDOR_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 650.0,
                            "offset_bearing_degrees": 90.0,
                        },
                        {
                            "location_id": EXCESSIVE_GEOMETRIC_DETOUR_ID,
                            "location_type": "Outdoor",
                            "status": "A",
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "distance_along_route_m": 500.0,
                            "route_offset_m": 580.0,
                            "offset_bearing_degrees": 270.0,
                        },
                    ],
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
                            :data_state,
                            :calculated_at
                        )
                        """
                    ),
                    [
                        {
                            "location_id": location_id,
                            "window_start": window_start,
                            "window_end": window_end,
                            "observed_rows": (
                                5 if location_id == LIVE_ID else 0
                            ),
                            "current_count": (
                                300 if location_id == LIVE_ID else None
                            ),
                            "data_state": (
                                "OK" if location_id == LIVE_ID else "NO_DATA"
                            ),
                            "calculated_at": calculated_at,
                        }
                        for location_id in TEST_IDS
                    ],
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO sensor_hour_daytype_baseline (
                            location_id,
                            hour_day,
                            day_type,
                            observation_count,
                            mean_count,
                            median_count,
                            p75,
                            baseline_start_date,
                            baseline_end_date
                        ) VALUES (
                            :location_id,
                            :hour_day,
                            :day_type,
                            :observation_count,
                            :mean_count,
                            :median_count,
                            :p75,
                            :baseline_start_date,
                            :baseline_end_date
                        )
                        """
                    ),
                    [
                        {
                            "location_id": LIVE_ID,
                            "hour_day": hour_day,
                            "day_type": day_type,
                            "observation_count": 50,
                            "mean_count": 720.0,
                            "median_count": 600.0,
                            "p75": 900.0,
                            "baseline_start_date": date(2024, 8, 10),
                            "baseline_end_date": date(2026, 2, 7),
                        },
                        {
                            "location_id": HISTORICAL_ID,
                            "hour_day": hour_day,
                            "day_type": day_type,
                            "observation_count": 40,
                            "mean_count": 420.0,
                            "median_count": 300.0,
                            "p75": 540.0,
                            "baseline_start_date": date(2024, 8, 10),
                            "baseline_end_date": date(2026, 2, 7),
                        },
                    ],
                )

                expected_locations = {
                    int(row["location_id"]): (
                        float(row["longitude"]),
                        float(row["latitude"]),
                    )
                    for row in connection.execute(
                        text(
                            """
                            SELECT location_id, longitude, latitude
                            FROM sensor_location_current
                            WHERE location_id = ANY(CAST(:test_ids AS BIGINT[]))
                            """
                        ),
                        {"test_ids": [LIVE_ID, HISTORICAL_ID]},
                    ).mappings()
                }
                fixture_metrics = {
                    int(row["location_id"]): row
                    for row in connection.execute(
                        text(
                            """
                            WITH journey AS (
                                SELECT
                                    ST_SetSRID(
                                        ST_MakePoint(
                                            :origin_longitude,
                                            :origin_latitude
                                        ), 4326
                                    )::geography AS origin_geom,
                                    ST_SetSRID(
                                        ST_MakePoint(
                                            :destination_longitude,
                                            :destination_latitude
                                        ), 4326
                                    )::geography AS destination_geom,
                                    ST_SetSRID(
                                        ST_GeomFromGeoJSON(:route_geojson),
                                        4326
                                    )::geography AS route_geom
                            )
                            SELECT
                                location.location_id,
                                location.location_type,
                                location.status,
                                ST_Distance(
                                    location.geom, journey.origin_geom
                                ) AS origin_distance_m,
                                ST_Distance(
                                    location.geom, journey.destination_geom
                                ) AS destination_distance_m,
                                ST_Distance(
                                    location.geom, journey.route_geom
                                ) AS route_distance_m,
                                ST_Distance(
                                    journey.origin_geom,
                                    journey.destination_geom
                                ) AS direct_distance_m
                            FROM sensor_location_current location
                            CROSS JOIN journey
                            WHERE location.location_id = ANY(
                                CAST(:test_ids AS BIGINT[])
                            )
                            """
                        ),
                        {
                            "origin_longitude": ORIGIN[0],
                            "origin_latitude": ORIGIN[1],
                            "destination_longitude": destination_coordinate[0],
                            "destination_latitude": destination_coordinate[1],
                            "route_geojson": direct_route.model_dump_json(),
                            "test_ids": list(TEST_IDS),
                        },
                    ).mappings()
                }

                for eligible_id in (LIVE_ID, HISTORICAL_ID):
                    metric = fixture_metrics[eligible_id]
                    assert 35.0 < metric["route_distance_m"] <= 600.0
                    assert metric["origin_distance_m"] >= 150.0
                    assert metric["destination_distance_m"] >= 150.0
                    assert (
                        metric["origin_distance_m"]
                        + metric["destination_distance_m"]
                        <= 1.5 * metric["direct_distance_m"]
                    )
                assert (
                    fixture_metrics[TOO_CLOSE_TO_ROUTE_ID]["route_distance_m"]
                    <= 35.0
                )
                assert (
                    fixture_metrics[TOO_CLOSE_TO_ORIGIN_ID]["origin_distance_m"]
                    < 150.0
                )
                assert (
                    fixture_metrics[TOO_CLOSE_TO_DESTINATION_ID][
                        "destination_distance_m"
                    ]
                    < 150.0
                )
                assert fixture_metrics[INACTIVE_ID]["status"] != "A"
                assert fixture_metrics[INDOOR_ID]["location_type"] != "Outdoor"
                assert (
                    fixture_metrics[OUTSIDE_CORRIDOR_ID]["route_distance_m"]
                    > 600.0
                )
                detour_metric = fixture_metrics[EXCESSIVE_GEOMETRIC_DETOUR_ID]
                assert 35.0 < detour_metric["route_distance_m"] <= 600.0
                assert detour_metric["origin_distance_m"] >= 150.0
                assert detour_metric["destination_distance_m"] >= 150.0
                assert (
                    detour_metric["origin_distance_m"]
                    + detour_metric["destination_distance_m"]
                    > 1.5 * detour_metric["direct_distance_m"]
                )

                result = RouteWaypointRepository(
                    connection=connection
                ).find_waypoint_evidence(
                    origin=ORIGIN,
                    destination=destination_coordinate,
                    direct_route_geometry=direct_route,
                )

                controlled = {
                    row.sensor_flow.location_id: row
                    for row in result.evidence
                    if row.sensor_flow.location_id in TEST_IDS
                }
                assert set(controlled) == {LIVE_ID, HISTORICAL_ID}
                assert result.sql_execution_count == 1
                assert result.snapshot.window_variant_count == 1
                assert result.snapshot.window_start == window_start
                assert result.snapshot.window_end == window_end
                assert result.snapshot.baseline_hour_day == hour_day
                assert result.snapshot.baseline_day_type == day_type

                live = controlled[LIVE_ID]
                assert live.longitude == pytest.approx(
                    expected_locations[LIVE_ID][0]
                )
                assert live.latitude == pytest.approx(
                    expected_locations[LIVE_ID][1]
                )
                assert live.distance_from_direct_route_meters == pytest.approx(
                    100.0, abs=0.1
                )
                assert live.distance_from_origin_meters >= 150.0
                assert live.distance_from_destination_meters >= 150.0
                assert live.sensor_flow.data_state == "OK"
                assert live.sensor_flow.current_15m_count == 300
                assert live.sensor_flow.current_15m_observed_rows == 5
                assert (
                    live.sensor_flow.live_pedestrian_movements_per_minute
                    == 20.0
                )
                assert live.sensor_flow.baseline_hour_day == hour_day
                assert live.sensor_flow.baseline_day_type == day_type
                assert live.sensor_flow.baseline_observation_count == 50
                assert live.sensor_flow.baseline_median_count == 600.0
                assert live.sensor_flow.baseline_mean_count == 720.0
                assert live.sensor_flow.baseline_p75_count == 900.0
                assert live.sensor_flow.baseline_start_date == date(2024, 8, 10)
                assert live.sensor_flow.baseline_end_date == date(2026, 2, 7)

                historical = controlled[HISTORICAL_ID]
                assert historical.longitude == pytest.approx(
                    expected_locations[HISTORICAL_ID][0]
                )
                assert historical.latitude == pytest.approx(
                    expected_locations[HISTORICAL_ID][1]
                )
                assert (
                    historical.distance_from_direct_route_meters
                    == pytest.approx(200.0, abs=0.1)
                )
                assert historical.sensor_flow.data_state == "NO_DATA"
                assert historical.sensor_flow.current_15m_count is None
                assert (
                    historical.sensor_flow.live_pedestrian_movements_per_minute
                    is None
                )
                assert historical.sensor_flow.baseline_hour_day == hour_day
                assert historical.sensor_flow.baseline_day_type == day_type
                assert historical.sensor_flow.baseline_observation_count == 40
                assert historical.sensor_flow.baseline_median_count == 300.0
                assert (
                    historical.sensor_flow
                    .historical_typical_movements_per_minute
                    == 5.0
                )
            finally:
                transaction.rollback()

        with engine.connect() as connection:
            after = connection.execute(_INTEGRITY_QUERY).mappings().one()
            controlled_rows = connection.execute(
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
        assert controlled_rows == 0
    finally:
        engine.dispose()
