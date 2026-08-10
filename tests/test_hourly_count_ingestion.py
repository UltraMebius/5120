from datetime import date

import pytest

from backend.app.services.ingestion.hourly_count_ingestion import (
    transform_hourly_record,
)


START_DATE = date(2025, 1, 4)
END_DATE = date(2025, 1, 4)


def _transform(source: dict[str, object]):
    return transform_hourly_record(
        source,
        start_date=START_DATE,
        end_date=END_DATE,
    )


def _valid_source(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "id": "251520250104",
        "location_id": "25",
        "sensing_date": "2025-01-04",
        "hourday": "15",
        "direction_1": "0",
        "direction_2": "0",
        "pedestriancount": "0",
        "sensor_name": "MCEC_T",
        "location": "-37.82401896, 144.95604426",
    }
    source.update(overrides)
    return source


def test_live_location_id_maps_to_natural_key_and_weekend_day_type() -> None:
    result = _transform(_valid_source())

    assert result.record is not None
    assert result.record.key == (25, date(2025, 1, 4), 15)
    assert result.record.day_type == "Weekend"
    assert result.record.source_id == 251520250104


def test_zero_count_is_preserved_as_an_observed_value() -> None:
    result = _transform(_valid_source(pedestriancount="0"))

    assert result.record is not None
    assert result.record.total_of_directions == 0
    assert result.skip_reason is None


@pytest.mark.parametrize("hour", ["-1", "24", "not-an-hour", ""])
def test_invalid_hours_are_rejected(hour: str) -> None:
    result = _transform(_valid_source(hourday=hour))

    assert result.record is None
    assert result.skip_reason == "missing_or_invalid_hour"


def test_negative_count_is_rejected() -> None:
    result = _transform(_valid_source(pedestriancount="-1"))

    assert result.record is None
    assert result.skip_reason == "negative_count"


@pytest.mark.parametrize("value", [None, ""])
def test_missing_count_is_not_converted_to_zero(value: object) -> None:
    result = _transform(_valid_source(pedestriancount=value))

    assert result.record is None
    assert result.skip_reason == "missing_count"


def test_directional_fields_are_optional() -> None:
    result = _transform(_valid_source(direction_1="", direction_2=None))

    assert result.record is not None
    assert result.record.direction_1 is None
    assert result.record.direction_2 is None


def test_malformed_sensing_date_is_rejected_without_timezone_conversion() -> None:
    result = _transform(_valid_source(sensing_date="04/01/2025"))

    assert result.record is None
    assert result.skip_reason == "missing_or_invalid_sensing_date"
