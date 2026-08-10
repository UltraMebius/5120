from datetime import date

import pytest

from backend.app.services.baseline.historical_baseline_service import (
    LOCAL_BASELINE_EXCLUDED_LOCATION_IDS,
    OBSERVED_UNRESOLVED_LOCATION_IDS,
    SENSOR_37_LOCAL_START_DATE,
    TRAINING_END_DATE,
    TRAINING_START_DATE,
    calculate_baseline_statistics,
    is_local_observation_eligible,
    is_network_observation_eligible,
    local_group_key,
    network_group_key,
)


def _local(location_id: int, sensing_date: date, **overrides: object) -> bool:
    values = {
        "location_id": location_id,
        "sensing_date": sensing_date,
        "location_type": "Outdoor",
        "status": "A",
    }
    values.update(overrides)
    return is_local_observation_eligible(**values)


def _network(location_id: int, sensing_date: date, **overrides: object) -> bool:
    values = {
        "location_id": location_id,
        "sensing_date": sensing_date,
        "location_type": "Outdoor",
        "status": "A",
    }
    values.update(overrides)
    return is_network_observation_eligible(**values)


def test_exact_project_training_window_and_holdout_exclusion() -> None:
    assert TRAINING_START_DATE == date(2024, 8, 10)
    assert TRAINING_END_DATE == date(2026, 2, 7)
    assert _local(14, TRAINING_START_DATE)
    assert _local(14, TRAINING_END_DATE)
    assert not _local(14, date(2024, 8, 9))
    assert not _local(14, date(2026, 2, 8))
    assert not _network(14, date(2026, 2, 8))


def test_only_active_outdoor_sensors_are_model_eligible() -> None:
    assert _local(14, TRAINING_START_DATE, location_type=" outdoor ")
    assert not _local(14, TRAINING_START_DATE, location_type="Indoor")
    assert not _network(14, TRAINING_START_DATE, status="I")
    assert not _network(14, TRAINING_START_DATE, status=None)


@pytest.mark.parametrize("location_id", OBSERVED_UNRESOLVED_LOCATION_IDS)
def test_unresolved_source_ids_are_excluded_from_both_models(
    location_id: int,
) -> None:
    assert not _local(location_id, TRAINING_START_DATE)
    assert not _network(location_id, TRAINING_START_DATE)


def test_sensor_14_uses_the_full_frozen_window() -> None:
    assert _local(14, TRAINING_START_DATE)
    assert _local(14, TRAINING_END_DATE)


def test_sensor_37_local_date_cut_is_inclusive_from_august_12() -> None:
    assert SENSOR_37_LOCAL_START_DATE == date(2024, 8, 12)
    assert not _local(37, date(2024, 8, 10))
    assert not _local(37, date(2024, 8, 11))
    assert _local(37, date(2024, 8, 12))
    assert _network(37, date(2024, 8, 10))


@pytest.mark.parametrize("location_id", LOCAL_BASELINE_EXCLUDED_LOCATION_IDS)
def test_47_and_181_are_local_only_exclusions(location_id: int) -> None:
    assert not _local(location_id, date(2025, 5, 1))
    assert _network(location_id, date(2025, 5, 1))


def test_local_and_network_grouping_contracts_are_distinct() -> None:
    assert local_group_key(14, 8, "Weekday") == (14, 8, "Weekday")
    assert network_group_key(8, "Weekday") == (8, "Weekday")


def test_continuous_percentiles_match_deterministic_linear_fixture() -> None:
    statistics = calculate_baseline_statistics([0, 10, 20, 30, 40])

    assert statistics.observation_count == 5
    assert statistics.mean_count == 20
    assert statistics.median_count == statistics.p50 == 20
    assert statistics.p10 == 4
    assert statistics.p20 == 8
    assert statistics.p25 == 10
    assert statistics.p40 == 16
    assert statistics.p60 == 24
    assert statistics.p75 == 30
    assert statistics.p80 == 32
    assert statistics.p90 == 36
    assert statistics.p95 == 38


def test_zero_is_an_observation_and_no_minimum_support_was_invented() -> None:
    zero_only = calculate_baseline_statistics([0])

    assert zero_only.observation_count == 1
    assert zero_only.mean_count == 0
    assert zero_only.p10 == zero_only.p50 == zero_only.p95 == 0


@pytest.mark.parametrize("values", [[], [-1], [float("inf")]])
def test_invalid_statistic_fixtures_are_rejected(values: list[float]) -> None:
    with pytest.raises(ValueError):
        calculate_baseline_statistics(values)
