from datetime import datetime, timezone
from unittest.mock import MagicMock

from backend.app.repositories.spatial_repository import SpatialRepository


def test_postgis_neighbour_result_mapping_uses_lon_lat_and_metre_radius() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value

    candidate_result = MagicMock()
    candidate_result.mappings.return_value = [
        {
            "location_id": 11,
            "location_type": "Outdoor",
            "status": "A",
            "data_state": "OK",
            "current_15m_network_percentile": 75.0,
            "current_1h_local_historical_percentile": 40.0,
            "current_15m_window_start": datetime(
                2026, 8, 10, 8, 0, tzinfo=timezone.utc
            ),
            "current_15m_window_end": datetime(
                2026, 8, 10, 8, 15, tzinfo=timezone.utc
            ),
            "calculated_at": datetime(2026, 8, 10, 8, 20, tzinfo=timezone.utc),
            "distance_m": 12.5,
        }
    ]
    nearest_result = MagicMock()
    nearest_result.scalar_one_or_none.return_value = 12.5
    snapshot_result = MagicMock()
    snapshot_result.mappings.return_value.one.return_value = {
        "source_window_start": datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc),
        "source_window_end": datetime(2026, 8, 10, 8, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 8, 10, 8, 20, tzinfo=timezone.utc),
        "window_variant_count": 1,
    }
    connection.execute.side_effect = [
        candidate_result,
        nearest_result,
        snapshot_result,
    ]

    result = SpatialRepository(engine).find_neighbourhood(
        longitude=144.96,
        latitude=-37.81,
        maximum_radius_m=300,
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].location_id == 11
    assert result.candidates[0].distance_m == 12.5
    assert result.nearest_valid_sensor_distance_m == 12.5
    first_statement, first_parameters = connection.execute.call_args_list[0].args
    assert "ST_DWithin" in str(first_statement)
    assert "ST_Distance" in str(first_statement)
    assert "ST_MakePoint(:longitude, :latitude)" in str(first_statement)
    assert first_parameters == {
        "longitude": 144.96,
        "latitude": -37.81,
        "maximum_radius_m": 300,
    }
