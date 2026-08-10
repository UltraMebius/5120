from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.app.models.hourly_count import HourlyCountRecord
from backend.app.repositories.hourly_count_repository import HourlyCountRepository


def _record(location_id: int, count: int = 0) -> HourlyCountRecord:
    return HourlyCountRecord(
        location_id=location_id,
        sensing_date=date(2025, 1, 4),
        hour_day=15,
        day_type="Weekend",
        source_id=251520250104,
        direction_1=0,
        direction_2=0,
        total_of_directions=count,
        source_sensor_name="MCEC_T",
        source_location_text="-37.82401896, 144.95604426",
    )


def _mock_engine(existing_keys: list[tuple[int, date, int]]):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    sensor_result = MagicMock()
    sensor_result.scalars.return_value = iter([25])
    existing_rows = [
        SimpleNamespace(
            location_id=location_id,
            sensing_date=sensing_date,
            hour_day=hour_day,
        )
        for location_id, sensing_date, hour_day in existing_keys
    ]
    connection.execute.side_effect = [sensor_result, existing_rows, None]
    return engine, connection


def test_batch_upsert_preserves_zero_and_reports_unknown_sensor_ids() -> None:
    engine, connection = _mock_engine([])

    result = HourlyCountRepository(engine).upsert_hourly_counts(
        [_record(25, 0), _record(999, 10)]
    )

    assert result.inserted == 1
    assert result.updated == 0
    assert result.unknown_sensor_rows == 1
    assert result.unknown_sensor_ids == (999,)
    assert engine.begin.call_count == 1
    upsert_parameters = connection.execute.call_args_list[2].args[1]
    assert len(upsert_parameters) == 1
    assert upsert_parameters[0]["location_id"] == 25
    assert upsert_parameters[0]["total_of_directions"] == 0


def test_second_batch_run_updates_the_same_authoritative_key() -> None:
    key = (25, date(2025, 1, 4), 15)
    engine, _ = _mock_engine([key])

    result = HourlyCountRepository(engine).upsert_hourly_counts([_record(25, 5)])

    assert result.inserted == 0
    assert result.updated == 1
    assert result.unknown_sensor_rows == 0
