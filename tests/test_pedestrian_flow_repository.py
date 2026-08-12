from datetime import datetime, timezone
import json
from unittest.mock import MagicMock

import pytest

from backend.app.models.pedestrian_flow import FlowSamplePoint
from backend.app.repositories.pedestrian_flow_repository import (
    PedestrianFlowRepository,
)


WINDOW_START = datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 13, 1, 15, tzinfo=timezone.utc)


def _sample(route_index: int, sample_index: int) -> FlowSamplePoint:
    return FlowSamplePoint(
        route_index=route_index,
        sample_index=sample_index,
        distance_along_route_meters=float(sample_index * 50),
        longitude=144.96 + sample_index * 0.00001,
        latitude=-37.81,
    )


def _row(sample: FlowSamplePoint, *, location_id=None, distance=None):
    return {
        "route_index": sample.route_index,
        "sample_index": sample.sample_index,
        "distance_along_route_meters": sample.distance_along_route_meters,
        "longitude": sample.longitude,
        "latitude": sample.latitude,
        "snapshot_window_start": WINDOW_START,
        "snapshot_window_end": WINDOW_END,
        "snapshot_calculated_at": WINDOW_END,
        "window_variant_count": 1,
        "context_hour_day": 11,
        "context_day_type": "Weekday",
        "location_id": location_id,
        "location_type": "Outdoor" if location_id is not None else None,
        "status": "A" if location_id is not None else None,
        "distance_meters": distance,
        "data_state": "OK" if location_id is not None else None,
        "current_15m_count": 300 if location_id is not None else None,
        "current_15m_observed_rows": 10 if location_id is not None else None,
        "current_15m_window_start": WINDOW_START,
        "current_15m_window_end": WINDOW_END,
        "calculated_at": WINDOW_END,
        "baseline_hour_day": 11 if location_id is not None else None,
        "baseline_day_type": "Weekday" if location_id is not None else None,
        "baseline_observation_count": 50 if location_id is not None else None,
        "baseline_median_count": 600 if location_id is not None else None,
        "baseline_mean_count": 720 if location_id is not None else None,
        "baseline_p75_count": 900 if location_id is not None else None,
        "baseline_start_date": None,
        "baseline_end_date": None,
    }


def _repository(rows):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    result = MagicMock()
    result.mappings.return_value = rows
    connection.execute.return_value = result
    return PedestrianFlowRepository(engine), engine, connection


@pytest.mark.parametrize("sample_count", [1, 25, 75])
def test_batch_statement_count_is_fixed_for_any_sample_count(
    sample_count: int,
) -> None:
    samples = tuple(_sample(0, index) for index in range(sample_count))
    repository, engine, connection = _repository(
        [_row(sample) for sample in samples]
    )

    batch = repository.find_flow_neighbourhoods(samples)

    assert len(batch.neighbourhoods) == sample_count
    assert batch.sql_execution_count == 1
    assert connection.execute.call_count == 1
    assert engine.connect.call_count == 1
    statement, parameters = connection.execute.call_args.args
    assert "JSONB_TO_RECORDSET" in str(statement)
    assert "ST_DWithin" in str(statement)
    assert "sensor_hour_daytype_baseline" in str(statement)
    assert len(json.loads(parameters["samples"])) == sample_count
    assert parameters["maximum_radius_m"] == 300.0


def test_one_batch_maps_multiple_routes_back_to_route_and_sample_keys() -> None:
    samples = (
        _sample(0, 0),
        _sample(0, 1),
        _sample(1, 0),
        _sample(2, 0),
    )
    rows = [
        _row(samples[0], location_id=10, distance=25.0),
        _row(samples[0], location_id=11, distance=75.0),
        _row(samples[1]),
        _row(samples[2], location_id=20, distance=100.0),
        _row(samples[3], location_id=30, distance=200.0),
    ]
    repository, _, connection = _repository(rows)

    batch = repository.find_flow_neighbourhoods(samples)

    mapped = {
        neighbourhood.sample.key: tuple(
            sensor.location_id for sensor in neighbourhood.sensors
        )
        for neighbourhood in batch.neighbourhoods
    }
    assert mapped == {
        (0, 0): (10, 11),
        (0, 1): (),
        (1, 0): (20,),
        (2, 0): (30,),
    }
    assert connection.execute.call_count == 1
    assert batch.snapshot.baseline_hour_day == 11
    assert batch.snapshot.baseline_day_type == "Weekday"


def test_duplicate_route_sample_key_is_rejected_before_database_access() -> None:
    sample = _sample(0, 0)
    repository, engine, _ = _repository([])

    with pytest.raises(ValueError, match="unique"):
        repository.find_flow_neighbourhoods([sample, sample])

    engine.connect.assert_not_called()


def test_empty_batch_does_not_checkout_or_execute_database_statement() -> None:
    repository, engine, connection = _repository([])

    batch = repository.find_flow_neighbourhoods([])

    assert batch.neighbourhoods == ()
    assert batch.sql_execution_count == 0
    engine.connect.assert_not_called()
    connection.execute.assert_not_called()
