from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from backend.app.models.pedestrian_flow import (
    FlowNeighbourhood,
    FlowNeighbourhoodBatch,
    FlowSamplePoint,
    PedestrianFlowSnapshot,
    SensorPedestrianFlow,
)
from backend.app.services.crowd.pedestrian_flow_service import (
    PedestrianFlowService,
)


WINDOW_START = datetime(2026, 8, 13, 1, 0, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 13, 1, 15, tzinfo=timezone.utc)
CALCULATED_AT = datetime(2026, 8, 13, 1, 20, tzinfo=timezone.utc)
SNAPSHOT = PedestrianFlowSnapshot(
    window_start=WINDOW_START,
    window_end=WINDOW_END,
    calculated_at=CALCULATED_AT,
    window_variant_count=1,
    baseline_hour_day=11,
    baseline_day_type="Weekday",
)


def _sample(route_index=0, sample_index=0) -> FlowSamplePoint:
    return FlowSamplePoint(
        route_index=route_index,
        sample_index=sample_index,
        distance_along_route_meters=float(sample_index * 50),
        longitude=144.96,
        latitude=-37.81,
    )


def _sensor(
    location_id: int = 1,
    *,
    distance: float = 100.0,
    state: str = "OK",
    count: int | None = 300,
    observed_rows: int | None = 15,
    median: float | None = 600.0,
    mean: float | None = 720.0,
    p75: float | None = 900.0,
    location_type: str = "Outdoor",
    status: str | None = "A",
) -> SensorPedestrianFlow:
    return SensorPedestrianFlow(
        location_id=location_id,
        distance_meters=distance,
        location_type=location_type,
        status=status,
        data_state=state,
        current_15m_count=count,
        current_15m_observed_rows=observed_rows,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        calculated_at=CALCULATED_AT,
        baseline_hour_day=11,
        baseline_day_type="Weekday",
        baseline_observation_count=50,
        baseline_median_count=median,
        baseline_mean_count=mean,
        baseline_p75_count=p75,
        baseline_start_date=date(2024, 8, 10),
        baseline_end_date=date(2026, 2, 7),
    )


class FakeRepository:
    def __init__(self, neighbourhoods):
        self.neighbourhoods = tuple(neighbourhoods)
        self.calls = []

    def find_flow_neighbourhoods(self, samples, *, maximum_radius_m):
        self.calls.append((tuple(samples), maximum_radius_m))
        return FlowNeighbourhoodBatch(
            neighbourhoods=self.neighbourhoods,
            snapshot=SNAPSHOT,
            database_elapsed_ms=4.5,
            sql_execution_count=1,
        )


def _evaluate(*sensors: SensorPedestrianFlow):
    sample = _sample()
    repository = FakeRepository([FlowNeighbourhood(sample, tuple(sensors))])
    result = PedestrianFlowService(repository).evaluate_samples([sample])
    assert repository.calls == [((sample,), 300.0)]
    return result.samples[0]


def test_live_fixed_window_rate_is_current_count_divided_by_15() -> None:
    assert _sensor(count=300).live_pedestrian_movements_per_minute == 20.0


def test_live_explicit_zero_remains_numeric_zero() -> None:
    assert _sensor(count=0).live_pedestrian_movements_per_minute == 0.0


def test_live_rate_never_uses_observed_rows_as_denominator() -> None:
    sensor = _sensor(count=150, observed_rows=5)

    assert sensor.live_pedestrian_movements_per_minute == 10.0
    assert sensor.live_pedestrian_movements_per_minute != 30.0


@pytest.mark.parametrize(
    "state",
    ["AMBIGUOUS_NO_RECORD", "CONFLICTED", "STALE", "NO_DATA"],
)
def test_invalid_current_states_never_produce_live_flow(state: str) -> None:
    assert _sensor(state=state).live_pedestrian_movements_per_minute is None


def test_missing_or_invalid_current_count_never_produces_live_flow() -> None:
    assert _sensor(count=None).live_pedestrian_movements_per_minute is None
    assert _sensor(count=-1).live_pedestrian_movements_per_minute is None


def test_historical_hourly_statistics_are_explicit_average_rates() -> None:
    sensor = _sensor(median=600, mean=720, p75=900)

    assert sensor.historical_typical_movements_per_minute == 10.0
    assert sensor.historical_mean_movements_per_minute == 12.0
    assert sensor.historical_p75_movements_per_minute == 15.0
    assert sensor.historical_typical_statistic_basis == "hourly_median_count"
    assert sensor.baseline_observation_count == 50
    assert sensor.baseline_hour_day == 11
    assert sensor.baseline_day_type == "Weekday"


def test_live_point_flow_is_normalized_inverse_distance_not_a_sum() -> None:
    result = _evaluate(
        _sensor(1, distance=100, count=150, median=None),
        _sensor(2, distance=200, count=450, median=None),
    )

    assert result.live_pedestrian_movements_per_minute == pytest.approx(
        (10.0 / 100.0 + 30.0 / 200.0) / (1.0 / 100.0 + 1.0 / 200.0)
    )
    assert result.live_pedestrian_movements_per_minute != 40.0
    assert result.live_contributor_count == 2
    assert sum(
        row.normalised_weight for row in result.live_contributions
    ) == pytest.approx(1.0)


def test_historical_point_flow_is_weighted_separately_from_live() -> None:
    result = _evaluate(
        _sensor(1, distance=100, state="AMBIGUOUS_NO_RECORD", median=600),
        _sensor(2, distance=200, state="OK", count=300, median=1800),
    )

    assert result.live_pedestrian_movements_per_minute == 20.0
    assert result.live_contributor_count == 1
    assert result.historical_typical_movements_per_minute == pytest.approx(
        (10.0 / 100.0 + 30.0 / 200.0) / (1.0 / 100.0 + 1.0 / 200.0)
    )
    assert result.historical_contributor_count == 2


def test_historical_value_never_becomes_fake_live_flow() -> None:
    result = _evaluate(
        _sensor(state="AMBIGUOUS_NO_RECORD", count=None, median=600)
    )

    assert result.live_pedestrian_movements_per_minute is None
    assert result.live_support_status == "NO_DATA"
    assert result.historical_typical_movements_per_minute == 10.0
    assert result.historical_support_status == "SUPPORTED"


def test_distance_floor_clamps_zero_distance_without_division_by_zero() -> None:
    result = _evaluate(
        _sensor(1, distance=0.0, count=150, median=None),
        _sensor(2, distance=1.0, count=450, median=None),
    )

    assert result.live_pedestrian_movements_per_minute == pytest.approx(20.0)
    assert [
        row.normalised_weight for row in result.live_contributions
    ] == pytest.approx([0.5, 0.5])


@pytest.mark.parametrize(
    "overrides",
    [
        {"weighting_power": 2},
        {"distance_floor_m": 0.5},
    ],
)
def test_pedestrian_flow_weighting_formula_is_frozen(overrides: dict) -> None:
    with pytest.raises(ValueError, match="pedestrian flow requires"):
        PedestrianFlowService(FakeRepository([]), **overrides)


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (250.0, "SUPPORTED"),
        (250.001, "LIMITED"),
        (300.0, "LIMITED"),
        (300.001, "NO_DATA"),
    ],
)
def test_live_and_historical_support_respect_fixed_radii(
    distance: float,
    expected: str,
) -> None:
    result = _evaluate(_sensor(distance=distance))

    assert result.live_support_status == expected
    assert result.historical_support_status == expected
    if expected == "NO_DATA":
        assert result.live_pedestrian_movements_per_minute is None
        assert result.historical_typical_movements_per_minute is None


def test_indoor_and_inactive_sensors_never_contribute() -> None:
    result = _evaluate(
        _sensor(1, location_type="Indoor"),
        replace(_sensor(2), status="I"),
    )

    assert result.live_contributor_count == 0
    assert result.historical_contributor_count == 0
    assert result.live_pedestrian_movements_per_minute is None
    assert result.historical_typical_movements_per_minute is None
