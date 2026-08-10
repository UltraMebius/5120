import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.app.services.ingestion.city_sensor_client import CitySensorSnapshot
from backend.app.services.ingestion.sensor_location_ingestion import (
    SensorLocationIngestionService,
    transform_sensor_records,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "city_sensor_locations_sample.json"
)


def _source_records() -> list[dict[str, object]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return payload["results"]


def test_live_location_id_and_metadata_map_to_authoritative_fields() -> None:
    validation = transform_sensor_records(_source_records())
    record = validation.records[0]

    assert record.location_id == 3
    assert record.sensor_description == "Melbourne Central"
    assert record.sensor_name == "Swa295_T"
    assert record.installation_date.isoformat() == "2009-03-25"
    assert record.location_type == "Outdoor"
    assert record.status == "A"
    assert record.direction_1_label == "North"
    assert record.direction_2_label == "South"
    assert record.latitude == -37.81101524
    assert record.longitude == 144.96429485
    assert record.has_usable_location


def test_sensor_id_is_not_guessed_when_location_id_is_missing() -> None:
    validation = transform_sensor_records(
        [{"sensor_id": 3, "latitude": -37.81, "longitude": 144.96}]
    )

    assert validation.records == ()
    assert validation.skipped_records[0].reason == "missing_or_invalid_location_id"


def test_inactive_and_indoor_source_values_are_preserved() -> None:
    validation = transform_sensor_records(_source_records())
    inactive = validation.records[1]

    assert inactive.status == "I"
    assert inactive.location_type == "Indoor"
    assert inactive.note == "Retained inactive test metadata"
    assert inactive.has_usable_location


def test_missing_or_invalid_coordinates_preserve_sensor_without_location() -> None:
    source_records = _source_records()
    source_records.append(
        {
            "location_id": 9003,
            "location_type": "Outdoor",
            "latitude": -91,
            "longitude": 144.96,
        }
    )
    validation = transform_sensor_records(source_records)

    missing = next(
        record for record in validation.records if record.location_id == 9002
    )
    invalid = next(
        record for record in validation.records if record.location_id == 9003
    )
    assert not missing.has_usable_location
    assert not invalid.has_usable_location
    assert validation.location_skip_reason_counts == {
        "missing_coordinates": 1,
        "invalid_coordinates": 1,
    }


def test_disagreeing_nested_coordinates_are_not_written() -> None:
    source = _source_records()[0]
    source["location"] = {"lon": 144.0, "lat": -37.0}

    validation = transform_sensor_records([source])

    assert not validation.records[0].has_usable_location
    assert validation.skipped_locations[0].reason == "coordinate_fields_disagree"


def test_dry_run_never_calls_repository() -> None:
    records = tuple(_source_records())
    client = MagicMock()
    client.fetch_all.return_value = CitySensorSnapshot(
        total_count=len(records),
        records=records,
        observed_fields=tuple(sorted(records[0])),
    )
    repository = MagicMock()

    result = SensorLocationIngestionService(client, repository).run(dry_run=True)

    assert result.dry_run
    repository.upsert_sensor_locations.assert_not_called()
