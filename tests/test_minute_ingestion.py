import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.app.services.ingestion.minute_ingestion import (
    MinuteRecordError,
    transform_minute_record,
    transform_minute_records,
)


FIXTURE = Path(__file__).parent / "fixtures" / "city_minute_counts_sample.json"
AS_OF = datetime.fromisoformat("2026-08-10T10:30:00+10:00")


def _records():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]


def test_live_shape_maps_actual_location_and_timezone_aware_datetime() -> None:
    result = transform_minute_records(_records(), as_of=AS_OF)

    assert result.invalid_record_count == 0
    assert [row.location_id for row in result.observations] == [11, 25, 37]
    assert result.observations[0].source_sensing_datetime.utcoffset() is not None
    assert result.observations[0].sensing_date_local.isoformat() == "2026-08-10"
    assert result.observations[0].sensing_time_local.isoformat() == "10:15:00"


def test_explicit_zero_is_preserved_but_absent_minutes_are_not_created() -> None:
    result = transform_minute_records(_records(), as_of=AS_OF)

    assert len(result.observations) == 3
    zero = next(row for row in result.observations if row.location_id == 25)
    assert zero.total_of_directions == 0


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("direction_1", -1, "direction_1_negative"),
        ("direction_2", -1, "direction_2_negative"),
        ("total_of_directions", -1, "total_of_directions_negative"),
    ],
)
def test_negative_counts_are_rejected(field: str, value: int, reason: str) -> None:
    row = {**_records()[0], field: value}
    with pytest.raises(MinuteRecordError, match=reason):
        transform_minute_record(row, as_of=AS_OF)


def test_direction_total_mismatch_is_rejected() -> None:
    row = {**_records()[0], "total_of_directions": 99}
    with pytest.raises(MinuteRecordError, match="direction_total_mismatch"):
        transform_minute_record(row, as_of=AS_OF)


def test_future_timestamp_is_rejected() -> None:
    row = {
        **_records()[0],
        "sensing_datetime": "2026-08-10T10:31:00+10:00",
        "sensing_time": "10:31:00",
    }
    with pytest.raises(MinuteRecordError, match="future_sensing_datetime"):
        transform_minute_record(row, as_of=AS_OF)


def test_payload_hash_is_stable_for_equivalent_offset_instants() -> None:
    original = transform_minute_record(_records()[0], as_of=AS_OF)
    utc_row = {
        **_records()[0],
        "sensing_datetime": "2026-08-10T00:15:00Z",
    }
    equivalent = transform_minute_record(utc_row, as_of=AS_OF)
    assert original.payload_hash == equivalent.payload_hash
