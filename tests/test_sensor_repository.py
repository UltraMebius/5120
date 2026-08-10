from datetime import date
from unittest.mock import MagicMock

from backend.app.models.sensor import SensorLocationRecord
from backend.app.repositories.sensor_repository import SensorRepository


def _record(*, status: str = "I") -> SensorLocationRecord:
    return SensorLocationRecord(
        location_id=3,
        sensor_description="Melbourne Central",
        sensor_name="Swa295_T",
        installation_date=date(2009, 3, 25),
        note="Preserve this note",
        location_type="Outdoor",
        status=status,
        direction_1_label="North",
        direction_2_label="South",
        latitude=-37.81101524,
        longitude=144.96429485,
    )


def _mock_engine(
    existing_sensors: set[int], existing_locations: set[int]
) -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    sensor_result = MagicMock()
    sensor_result.scalars.return_value = iter(existing_sensors)
    location_result = MagicMock()
    location_result.scalars.return_value = iter(existing_locations)
    connection.execute.side_effect = [sensor_result, location_result, None, None]
    return engine, connection


def test_repository_uses_transactional_upserts_and_lon_lat_geometry_order() -> None:
    engine, connection = _mock_engine(set(), set())

    result = SensorRepository(engine).upsert_sensor_locations([_record()])

    assert result.sensors_inserted == 1
    assert result.locations_inserted == 1
    assert engine.begin.call_count == 1
    location_call = connection.execute.call_args_list[3]
    statement = str(location_call.args[0])
    parameters = location_call.args[1][0]
    assert "ON CONFLICT (location_id) DO UPDATE" in statement
    assert "ST_MakePoint(:longitude, :latitude)" in statement
    assert parameters["longitude"] == 144.96429485
    assert parameters["latitude"] == -37.81101524
    assert parameters["status"] == "I"
    assert parameters["note"] == "Preserve this note"


def test_repository_second_run_updates_without_duplicate_inserts() -> None:
    engine, _ = _mock_engine({3}, {3})

    result = SensorRepository(engine).upsert_sensor_locations([_record(status="A")])

    assert result.sensors_inserted == 0
    assert result.sensors_updated == 1
    assert result.locations_inserted == 0
    assert result.locations_updated == 1


def test_repository_removes_stale_location_when_coordinates_become_unusable() -> None:
    engine, connection = _mock_engine({3}, {3})
    unusable_record = SensorLocationRecord(
        location_id=3,
        sensor_description="Melbourne Central",
        sensor_name="Swa295_T",
        installation_date=None,
        note="Coordinates temporarily unavailable",
        location_type="Outdoor",
        status="I",
        direction_1_label=None,
        direction_2_label=None,
        latitude=None,
        longitude=None,
    )

    result = SensorRepository(engine).upsert_sensor_locations([unusable_record])

    assert result.sensors_updated == 1
    assert result.locations_removed == 1
    assert len(connection.execute.call_args_list) == 4
    assert "DELETE FROM sensor_location_current" in str(
        connection.execute.call_args_list[3].args[0]
    )
