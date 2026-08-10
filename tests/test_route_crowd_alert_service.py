from dataclasses import replace

import pytest

from backend.app.models.crowd import CrowdPreference
from backend.app.models.spatial import PointCrowdEstimate
from backend.app.services.routing.route_crowd_alert_service import (
    RouteCrowdAlertConfigurationError,
    RouteCrowdAlertDataConsistencyError,
    RouteCrowdAlertReason,
    RouteCrowdAlertService,
    RouteCrowdAlertState,
)
from backend.app.services.routing.route_crowd_evaluation_service import (
    RouteCrowdEvaluation,
    RouteSampleCrowdResult,
)
from backend.app.services.routing.route_sampling_service import RouteSample


Entry = tuple[str, object]


def _entry(status: str, score: object) -> Entry:
    return status, score


def _evaluation(
    entries: list[Entry],
    *,
    distances: list[float] | None = None,
    indexes: list[int] | None = None,
    route_id: str = "controlled-route",
) -> RouteCrowdEvaluation:
    sample_distances = distances or [float(index * 50) for index in range(len(entries))]
    sample_indexes = indexes or list(range(len(entries)))
    results: list[RouteSampleCrowdResult] = []

    for index, distance, (status, score) in zip(
        sample_indexes,
        sample_distances,
        entries,
    ):
        sample = RouteSample(
            index=index,
            distance_along_route_meters=distance,
            longitude=144.96 + index / 1_000_000,
            latitude=-37.81,
        )
        has_support = status != "NO_DATA"
        results.append(
            RouteSampleCrowdResult(
                sample=sample,
                crowd=PointCrowdEstimate(
                    latitude=sample.latitude,
                    longitude=sample.longitude,
                    crowd_exposure_score=score,  # type: ignore[arg-type]
                    crowd_level=None,
                    local_condition_score=None,
                    local_condition=None,
                    coverage_status=status,
                    nearby_sensors=1 if has_support else 0,
                    nearby_active_outdoor_sensors=1 if has_support else 0,
                    supporting_sensors=1 if has_support else 0,
                    nearest_sensor_distance_m=100.0 if has_support else None,
                    supporting_score_stddev=None,
                    weighting_method="inverse_distance_1_over_d",
                    updated_at=None,
                    source_window_start=None,
                    source_window_end=None,
                    support_radius_m=300.0,
                    reason=None if has_support else "NO_VALID_CURRENT_SENSOR_AVAILABLE",
                    contributions=(),
                ),
            )
        )

    return RouteCrowdEvaluation(
        route_id=route_id,
        route_length_meters=max(sample_distances, default=0.0),
        sampling_interval_meters=50.0,
        sample_results=tuple(results),
    )


def _evaluate(
    entries: list[Entry],
    preference: CrowdPreference = CrowdPreference.AVOID_BUSY,
    *,
    current_progress_meters: float = 0.0,
    distances: list[float] | None = None,
):
    return RouteCrowdAlertService().evaluate_ahead(
        _evaluation(entries, distances=distances),
        preference,
        current_progress_meters,
    )


def test_two_adjacent_supported_samples_above_low_threshold_alert() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 70.0),
        ]
    )

    assert result.decision is RouteCrowdAlertState.ALERT
    assert result.reason is RouteCrowdAlertReason.CONSECUTIVE_ABOVE_PREFERENCE_DETECTED
    assert (
        result.trigger_start_sample_index,
        result.trigger_end_sample_index,
    ) == (1, 2)
    assert (
        result.first_trigger_exposure,
        result.second_trigger_exposure,
    ) == (60.0, 70.0)


def test_supported_and_limited_adjacent_samples_can_alert() -> None:
    result = _evaluate(
        [_entry("SUPPORTED", 10.0), _entry("SUPPORTED", 60.0), _entry("LIMITED", 70.0)]
    )

    assert result.decision is RouteCrowdAlertState.ALERT
    assert result.supported_samples == 1
    assert result.limited_samples == 1


def test_one_above_threshold_sample_only_is_clear() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 40.0),
        ]
    )

    assert result.decision is RouteCrowdAlertState.CLEAR
    assert result.reason is RouteCrowdAlertReason.NO_CONSECUTIVE_ABOVE_PREFERENCE
    assert result.trigger_sample_count is None


def test_no_data_between_above_threshold_samples_breaks_streak() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("NO_DATA", None),
            _entry("LIMITED", 70.0),
        ]
    )

    assert result.decision is RouteCrowdAlertState.CLEAR
    assert result.no_data_samples == 1


def test_at_threshold_numeric_sample_breaks_streak() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 50.0),
            _entry("SUPPORTED", 70.0),
        ]
    )

    assert result.decision is RouteCrowdAlertState.CLEAR


def test_threshold_equality_is_not_above_preference() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 0.0),
            _entry("SUPPORTED", 50.0),
            _entry("SUPPORTED", 50.01),
        ]
    )

    assert result.decision is RouteCrowdAlertState.CLEAR
    assert result.pct_above_preference_in_window == 50.0


def test_first_longer_streak_is_returned_in_full() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("LIMITED", 70.0),
            _entry("SUPPORTED", 80.0),
            _entry("SUPPORTED", 90.0),
            _entry("SUPPORTED", 40.0),
        ]
    )

    assert result.decision is RouteCrowdAlertState.ALERT
    assert result.trigger_start_sample_index == 1
    assert result.trigger_end_sample_index == 4
    assert result.trigger_sample_count == 4
    assert result.maximum_exposure_in_trigger == 90.0


def test_first_of_multiple_qualifying_streaks_is_selected() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 70.0),
            _entry("SUPPORTED", 40.0),
            _entry("SUPPORTED", 80.0),
            _entry("SUPPORTED", 90.0),
        ]
    )

    assert (
        result.trigger_start_sample_index,
        result.trigger_end_sample_index,
    ) == (1, 2)
    assert result.maximum_exposure_in_window == 90.0


def test_all_look_ahead_samples_no_data_is_insufficient() -> None:
    result = _evaluate(
        [_entry("NO_DATA", None), _entry("NO_DATA", None), _entry("NO_DATA", None)]
    )

    assert result.decision is RouteCrowdAlertState.INSUFFICIENT_DATA
    assert result.reason is RouteCrowdAlertReason.NO_USABLE_LOOK_AHEAD_CROWD_DATA
    assert result.look_ahead_coverage_pct == 0.0


def test_mixed_partial_data_returns_clear_with_exact_diagnostics() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("NO_DATA", None),
            _entry("LIMITED", 40.0),
        ]
    )

    assert result.decision is RouteCrowdAlertState.CLEAR
    assert result.total_look_ahead_samples == 3
    assert result.numeric_look_ahead_samples == 2
    assert result.supported_samples == 1
    assert result.limited_samples == 1
    assert result.no_data_samples == 1
    assert result.look_ahead_coverage_pct == pytest.approx(200 / 3)
    assert result.pct_above_preference_in_window == 50.0
    assert result.maximum_exposure_in_window == 60.0


def test_progress_at_route_end_has_no_ahead_window() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 70.0),
        ],
        current_progress_meters=100.0,
    )

    assert result.decision is RouteCrowdAlertState.INSUFFICIENT_DATA
    assert result.reason is RouteCrowdAlertReason.NO_SAMPLES_AHEAD
    assert result.total_look_ahead_samples == 0
    assert result.look_ahead_coverage_pct is None


def test_sample_exactly_at_current_progress_is_excluded() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 90.0),
            _entry("SUPPORTED", 40.0),
        ],
        current_progress_meters=50.0,
    )

    assert result.decision is RouteCrowdAlertState.CLEAR
    assert result.total_look_ahead_samples == 1
    assert result.maximum_exposure_in_window == 40.0


def test_sample_exactly_300_metres_ahead_is_included() -> None:
    entries = [_entry("SUPPORTED", 10.0)] * 5 + [
        _entry("SUPPORTED", 60.0),
        _entry("SUPPORTED", 70.0),
    ]
    result = _evaluate(entries)

    assert result.decision is RouteCrowdAlertState.ALERT
    assert result.trigger_end_distance_meters == 300.0
    assert result.window_end_meters == 300.0


def test_sample_beyond_300_metres_is_excluded() -> None:
    entries = [_entry("SUPPORTED", 10.0)] * 6 + [
        _entry("SUPPORTED", 60.0),
        _entry("SUPPORTED", 70.0),
    ]
    result = _evaluate(entries)

    assert result.decision is RouteCrowdAlertState.CLEAR
    assert result.maximum_exposure_in_window == 60.0
    assert result.total_look_ahead_samples == 6


def test_fewer_than_300_metres_remaining_uses_only_remaining_samples() -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 70.0),
        ],
        current_progress_meters=100.0,
    )

    assert result.decision is RouteCrowdAlertState.ALERT
    assert result.total_look_ahead_samples == 2
    assert result.trigger_end_distance_meters == 200.0


@pytest.mark.parametrize(
    ("preference", "score", "threshold"),
    [
        (CrowdPreference.AVOID_BUSY, 50.01, 50.0),
        (CrowdPreference.PREFER_QUIETER, 75.01, 75.0),
        (CrowdPreference.FLEXIBLE, 90.01, 90.0),
    ],
)
def test_authoritative_preference_thresholds(
    preference: CrowdPreference,
    score: float,
    threshold: float,
) -> None:
    result = _evaluate(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", score),
            _entry("LIMITED", score),
        ],
        preference,
    )

    assert result.decision is RouteCrowdAlertState.ALERT
    assert result.threshold == threshold


def test_no_numeric_evidence_does_not_fabricate_zero_metrics() -> None:
    result = _evaluate(
        [_entry("NO_DATA", 0.0), _entry("NO_DATA", 0.0), _entry("NO_DATA", 0.0)]
    )

    assert result.numeric_look_ahead_samples == 0
    assert result.maximum_exposure_in_window is None
    assert result.pct_above_preference_in_window is None
    assert result.maximum_exposure_in_trigger is None
    assert result.first_trigger_exposure is None
    assert result.second_trigger_exposure is None


def test_supported_samples_without_numeric_scores_are_not_usable() -> None:
    result = _evaluate(
        [_entry("SUPPORTED", 10.0), _entry("SUPPORTED", None), _entry("LIMITED", None)]
    )

    assert result.decision is RouteCrowdAlertState.INSUFFICIENT_DATA
    assert result.supported_samples == 1
    assert result.limited_samples == 1
    assert result.numeric_look_ahead_samples == 0


@pytest.mark.parametrize(
    "evaluation",
    [
        _evaluation(
            [_entry("SUPPORTED", 10.0), _entry("SUPPORTED", 60.0)],
            indexes=[0, 2],
        ),
        _evaluation(
            [_entry("SUPPORTED", 10.0), _entry("SUPPORTED", 60.0)],
            distances=[50.0, 0.0],
        ),
    ],
)
def test_noncontiguous_or_out_of_order_samples_are_rejected(
    evaluation: RouteCrowdEvaluation,
) -> None:
    with pytest.raises(RouteCrowdAlertDataConsistencyError):
        RouteCrowdAlertService().evaluate_ahead(
            evaluation,
            CrowdPreference.AVOID_BUSY,
        )


def test_reversing_phase3e_results_is_rejected_deterministically() -> None:
    evaluation = _evaluation(
        [
            _entry("SUPPORTED", 10.0),
            _entry("SUPPORTED", 60.0),
            _entry("SUPPORTED", 70.0),
        ]
    )
    reversed_evaluation = replace(
        evaluation,
        sample_results=tuple(reversed(evaluation.sample_results)),
    )

    with pytest.raises(RouteCrowdAlertDataConsistencyError):
        RouteCrowdAlertService().evaluate_ahead(
            reversed_evaluation,
            CrowdPreference.AVOID_BUSY,
        )


@pytest.mark.parametrize("score", [True, "60", float("nan"), -0.01, 100.01])
def test_invalid_eligible_scores_are_consistency_errors(score: object) -> None:
    evaluation = _evaluation(
        [_entry("SUPPORTED", 10.0), _entry("SUPPORTED", score)]
    )

    with pytest.raises(RouteCrowdAlertDataConsistencyError):
        RouteCrowdAlertService().evaluate_ahead(
            evaluation,
            CrowdPreference.AVOID_BUSY,
        )


def test_unknown_coverage_status_is_a_consistency_error() -> None:
    with pytest.raises(RouteCrowdAlertDataConsistencyError):
        _evaluate([_entry("SUPPORTED", 10.0), _entry("UNKNOWN", 60.0)])


@pytest.mark.parametrize("progress", [-0.01, float("nan"), float("inf"), True])
def test_invalid_current_progress_is_rejected(progress: object) -> None:
    with pytest.raises(ValueError):
        RouteCrowdAlertService().evaluate_ahead(
            _evaluation([_entry("SUPPORTED", 10.0)]),
            CrowdPreference.AVOID_BUSY,
            progress,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"look_ahead_distance_meters": 0},
        {"look_ahead_distance_meters": float("nan")},
        {"required_consecutive_samples": 1},
        {"required_consecutive_samples": True},
    ],
)
def test_invalid_alert_configuration_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(RouteCrowdAlertConfigurationError):
        RouteCrowdAlertService(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "thresholds",
    [
        {},
        {
            CrowdPreference.AVOID_BUSY: True,
            CrowdPreference.PREFER_QUIETER: 75.0,
            CrowdPreference.FLEXIBLE: 90.0,
        },
    ],
)
def test_invalid_preference_threshold_configuration_is_rejected(
    thresholds: dict[CrowdPreference, object],
) -> None:
    with pytest.raises(RouteCrowdAlertConfigurationError):
        RouteCrowdAlertService(
            preference_thresholds=thresholds,  # type: ignore[arg-type]
        )
