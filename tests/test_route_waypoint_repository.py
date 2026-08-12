from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from backend.app.schemas.routes import GeoJsonLineString
from backend.app.repositories.route_waypoint_repository import (
    RouteWaypointRepository,
)


NOW = datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc)


def _row():
    return {
        "location_id": 100,
        "location_type": "Outdoor",
        "status": "A",
        "candidate_longitude": 144.961,
        "candidate_latitude": -37.815,
        "distance_from_origin_meters": 500.0,
        "distance_from_destination_meters": 500.0,
        "distance_from_direct_route_meters": 100.0,
        "estimated_geometric_detour_meters": 50.0,
        "snapshot_window_start": NOW,
        "snapshot_window_end": NOW,
        "snapshot_calculated_at": NOW,
        "window_variant_count": 1,
        "context_hour_day": 11,
        "context_day_type": "Weekday",
        "data_state": "OK",
        "current_15m_count": 150,
        "current_15m_observed_rows": 5,
        "current_15m_window_start": NOW,
        "current_15m_window_end": NOW,
        "calculated_at": NOW,
        "baseline_hour_day": 11,
        "baseline_day_type": "Weekday",
        "baseline_observation_count": 50,
        "baseline_median_count": 600.0,
        "baseline_mean_count": 720.0,
        "baseline_p75_count": 900.0,
        "baseline_start_date": date(2025, 1, 1),
        "baseline_end_date": date(2026, 1, 1),
    }


def test_corridor_waypoint_lookup_uses_one_bounded_sql_execution() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    result = MagicMock()
    result.mappings.return_value = [_row()]
    connection.execute.return_value = result
    repository = RouteWaypointRepository(engine)

    batch = repository.find_waypoint_evidence(
        origin=(144.96, -37.82),
        destination=(144.96, -37.81),
        direct_route_geometry=GeoJsonLineString(
            coordinates=[(144.96, -37.82), (144.96, -37.81)]
        ),
    )

    assert engine.connect.call_count == 1
    assert connection.execute.call_count == 1
    statement, parameters = connection.execute.call_args.args
    sql = str(statement)
    assert "ST_DWithin" in sql
    assert "sensor_location_current" in sql
    assert "current_sensor_activity" in sql
    assert "sensor_hour_daytype_baseline" in sql
    assert "LOWER(TRIM(location.location_type)) = 'outdoor'" in sql
    assert "UPPER(TRIM(location.status)) = 'A'" in sql
    assert parameters["search_corridor_radius_m"] == 600.0
    assert parameters["minimum_endpoint_distance_m"] == 150.0
    assert parameters["minimum_route_offset_m"] == 35.0
    assert parameters["geometric_detour_multiplier"] == 1.5
    assert batch.sql_execution_count == 1
    assert len(batch.evidence) == 1
    evidence = batch.evidence[0]
    assert evidence.sensor_flow.location_id == 100
    assert evidence.sensor_flow.live_pedestrian_movements_per_minute == 10.0
    assert evidence.sensor_flow.historical_typical_movements_per_minute == 10.0
